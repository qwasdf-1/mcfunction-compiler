package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.OperationArgument;
import net.minecraft.commands.arguments.ScoreHolderArgument;
import net.minecraft.commands.execution.UnboundEntryAction;
import net.minecraft.commands.execution.tasks.BuildContexts;
import net.minecraft.commands.functions.CommandFunction;
import net.minecraft.commands.functions.PlainTextFunction;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.ScoreboardCommand;
import net.minecraft.world.scores.ScoreHolder;
import dev.functioncompiler.mixin.BuildContextsAccessor;
import dev.functioncompiler.mixin.CommandContextAccessor;
import dev.functioncompiler.mixin.ContextChainAccessor;
import net.minecraft.advancements.predicates.MinMaxBounds;
import net.minecraft.commands.arguments.EntityAnchorArgument;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.commands.arguments.selector.EntitySelector;
import net.minecraft.commands.arguments.coordinates.Coordinates;
import net.minecraft.server.level.ServerLevel;
import net.minecraft.world.entity.Entity;

import java.util.ArrayList;
import java.util.Collection;
import java.util.List;

/**
 * Opt-in, narrow parsed-command prototype for literal fake-holder scoreboard
 * additions. It replaces only the Brigadier command callback, leaving
 * BuildContexts, ExecuteCommand, quota charging, result callbacks, and tracing
 * on the vanilla scheduler path.
 */
public final class ScoreAddPrototype {
    private ScoreAddPrototype() {
    }

    public static void compile(CommandFunction<?> function) {
        if (!(function instanceof PlainTextFunction<?> plainFunction)) {
            return;
        }

        compile(plainFunction, plainFunction.id());
    }

    public static void compile(PlainTextFunction<?> function, Identifier metricsId) {
        for (UnboundEntryAction<?> entry : function.entries()) {
            if (entry instanceof BuildContexts.Unbound<?> buildContexts) {
                compileEntry(buildContexts, metricsId);
            }
        }
    }

    @SuppressWarnings("unchecked")
    private static void compileEntry(
            BuildContexts.Unbound<?> buildContexts,
            Identifier functionId
    ) {
        ContextChain<CommandSourceStack> chain;
        try {
            chain = ((BuildContextsAccessor<CommandSourceStack>) buildContexts)
                    .functionCompiler$getCommand();
        } catch (ClassCastException exception) {
            return;
        }
        if (chain.getStage() != ContextChain.Stage.EXECUTE) {
            compileChainedModifiers(buildContexts, chain, functionId);
            return;
        }

        CommandContext<CommandSourceStack> context = chain.getTopContext();
        if (compileScoreAdd(context, functionId)) {
            return;
        }
        if (compileScoreOperation(context, functionId)) {
            return;
        }
        if (compileScoreReset(context, functionId)) {
            return;
        }
        if (DataStorageParser.compile(context, functionId)) {
            return;
        }
        if (StateMachineParser.compile(context, functionId)) {
            return;
        }
        LeafFunctionParser.compile(context, functionId);
    }

    @SuppressWarnings("unchecked")
    private static void compileChainedModifiers(
            BuildContexts.Unbound<?> buildContexts,
            ContextChain<CommandSourceStack> chain,
            Identifier functionId
    ) {
        ContextChainAccessor<CommandSourceStack> chainAccessor;
        try {
            chainAccessor = (ContextChainAccessor<CommandSourceStack>) (Object) chain;
        } catch (ClassCastException exception) {
            return;
        }

        List<CommandContext<CommandSourceStack>> modifiers =
                chainAccessor.functionCompiler$getModifiers();
        CommandContext<CommandSourceStack> executable =
                chainAccessor.functionCompiler$getExecutable();
        if (modifiers == null || modifiers.isEmpty() || executable == null) {
            return;
        }

        if (!compileExecutable(executable, functionId)) {
            return;
        }

        List<Object> parsedModifiers = parseModifiers(modifiers);
        if (parsedModifiers == null) {
            return;
        }

        Command<CommandSourceStack> wrapped = wrapModifiers(
                chain, parsedModifiers, executable.getCommand(), functionId
        );

        CommandContextAccessor<CommandSourceStack> execAccessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) executable;
        execAccessor.functionCompiler$setCommand(wrapped);

        BuildContextsAccessor<CommandSourceStack> buildContextsAccessor =
                (BuildContextsAccessor<CommandSourceStack>) (Object) buildContexts;
        buildContextsAccessor.functionCompiler$setCommand(
                new ContextChain<>(List.of(), executable)
        );
        ProbeMetrics.scoreAddCompiled(functionId);
    }

    @FunctionalInterface
    private interface ExecutableCompiler {
        boolean compile(CommandContext<CommandSourceStack> executable, Identifier functionId);
    }

    private static final List<ExecutableCompiler> EXECUTABLE_COMPILERS = List.of(
            ScoreAddPrototype::compileScoreAdd,
            ScoreAddPrototype::compileScoreOperation,
            ScoreAddPrototype::compileScoreReset,
            DataStorageParser::compile,
            DataGetParser::compile,
            StateMachineParser::compile,
            SetblockParser::compile,
            VisualSoundParser::compile,
            BossbarParser::compile,
            EffectParser::compile,
            TitleParser::compile,
            ItemCommandParser::compile,
            GameplayCommandParser::compile,
            LeafFunctionParser::compile,
            TailCallLoopParser::compile
    );

    private static boolean compileExecutable(
            CommandContext<CommandSourceStack> executable,
            Identifier functionId
    ) {
        for (ExecutableCompiler compiler : EXECUTABLE_COMPILERS) {
            if (compiler.compile(executable, functionId)) {
                return true;
            }
        }
        return false;
    }

    private static List<Object> parseModifiers(List<CommandContext<CommandSourceStack>> modifiers) {
        List<Object> result = new ArrayList<>();
        for (CommandContext<CommandSourceStack> mod : modifiers) {
            // 26.3 measured chain shape: the `run` literal redirects to the
            // dispatcher root with a null redirect modifier, so Brigadier's
            // ContextChain carries a trailing no-op modifier stage whose only
            // node is `run` for every `execute ... run ...` command. Vanilla
            // charges no quota debit for that stage and it transforms no
            // source; the executable is its child context. Skipping it is what
            // lets single-modifier chains compile at all. Any other stage that
            // no parser accepts still declines the whole chain, and because
            // every modifier parser requires the leading `execute` node, a
            // second real modifier stage still declines here — only
            // single-stage chains compile.
            if (nodeNames(mod).equals(List.of("run"))) {
                continue;
            }
            Object parsed = parseSingleModifier(mod);
            if (parsed == null) {
                return null;
            }
            result.add(parsed);
        }
        return result;
    }

    @FunctionalInterface
    private interface SingleModifierParser {
        Object parse(CommandContext<CommandSourceStack> mod);
    }

    private static final List<SingleModifierParser> MODIFIER_PARSERS = List.of(
            ScoreAddPrototype::parseScoreCondition,
            ScoreAddPrototype::parseScoreStore,
            DataStoreParser::parse,
            PredicateModifierParser::parse,
            ForkModifierParser::parse,
            ItemPredicateParser::parse,
            ScoreAddPrototype::parseContextModifier
    );

    private static Object parseSingleModifier(CommandContext<CommandSourceStack> mod) {
        for (SingleModifierParser parser : MODIFIER_PARSERS) {
            Object parsed = parser.parse(mod);
            if (parsed != null) {
                return parsed;
            }
        }
        return null;
    }

    private static Command<CommandSourceStack> wrapModifiers(
            ContextChain<CommandSourceStack> chain,
            List<Object> parsedModifiers,
            Command<CommandSourceStack> executableCommand,
            Identifier functionId
    ) {
        Command<CommandSourceStack> current = executableCommand;
        List<ContextModifierCommand.Transformation> pending = new ArrayList<>();

        for (int i = parsedModifiers.size() - 1; i >= 0; i--) {
            Object mod = parsedModifiers.get(i);
            if (mod instanceof ContextModifierCommand.Transformation transform) {
                pending.add(0, transform);
                continue;
            }
            if (mod instanceof ForkModifierParser.ParsedFork fork) {
                current = new InlinedForkingCommand(
                        chain, fork.resolver(), fork.transformer(), List.copyOf(pending), current, functionId
                );
                pending.clear();
                continue;
            }
            if (!pending.isEmpty()) {
                current = new ContextModifierCommand(chain, List.copyOf(pending), current, functionId);
                pending.clear();
            }
            current = wrapSingleModifier(chain, mod, current, functionId);
        }

        if (!pending.isEmpty()) {
            current = new ContextModifierCommand(chain, List.copyOf(pending), current, functionId);
        }
        return current;
    }

    private static Command<CommandSourceStack> wrapSingleModifier(
            ContextChain<CommandSourceStack> chain,
            Object mod,
            Command<CommandSourceStack> current,
            Identifier functionId
    ) {
        if (mod instanceof ParsedCondition pc) {
            return new ScoreConditionCommand(
                    chain, pc.targetHolder(), pc.isTargetSelf(), pc.targetObjective(),
                    pc.operator(), pc.sourceHolder(), pc.isSourceSelf(), pc.sourceObjective(),
                    pc.range(), pc.unless(), current, functionId
            );
        }
        if (mod instanceof ParsedStore ps) {
            return new ScoreStoreCommand(
                    chain, ps.targetHolder(), ps.isTargetSelf(), ps.objective(),
                    ps.isResult(), current, functionId
            );
        }
        if (mod instanceof DataStoreParser.ParsedDataStore pds) {
            return new DataStoreCommand(
                    chain, pds.storageId(), pds.path(), pds.type(), pds.scale(),
                    pds.isResult(), current, functionId
            );
        }
        if (mod instanceof PredicateModifierParser.ParsedPredicate pp) {
            return new PredicateConditionCommand(
                    chain, pp.evaluator(), pp.unless(), current, functionId
            );
        }
        return current;
    }

    @FunctionalInterface
    private interface ModifierParser {
        ContextModifierCommand.Transformation parse(
                CommandContext<CommandSourceStack> context,
                List<String> names
        );
    }

    private static final java.util.Map<String, ModifierParser> CONTEXT_PARSERS = java.util.Map.of(
            "as", ScoreAddPrototype::parseAsModifier,
            "at", ScoreAddPrototype::parseAtModifier,
            "positioned", ScoreAddPrototype::parsePositionedModifier,
            "rotated", ScoreAddPrototype::parseRotatedModifier,
            "anchored", ScoreAddPrototype::parseAnchoredModifier,
            "in", SpatialModifierParser::parseInModifier,
            "align", SpatialModifierParser::parseAlignModifier,
            "facing", SpatialModifierParser::parseFacingModifier
    );

    private static ContextModifierCommand.Transformation parseContextModifier(
            CommandContext<CommandSourceStack> context
    ) {
        List<String> names = nodeNames(context);
        if (names.size() < 2 || !"execute".equals(names.get(0))) {
            return null;
        }
        ModifierParser parser = CONTEXT_PARSERS.get(names.get(1));
        return parser == null ? null : parser.parse(context, names);
    }

    private static ContextModifierCommand.Transformation parseAsModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"targets".equals(names.get(2))
                || !"@s".equals(extractNodeText(context, "targets"))) {
            return null;
        }
        return (ctx, source) -> source.getEntity() == null ? null : source.withEntity(source.getEntity());
    }

    private static ContextModifierCommand.Transformation parseAtModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"targets".equals(names.get(2))
                || !"@s".equals(extractNodeText(context, "targets"))) {
            return null;
        }
        return (ctx, source) -> {
            Entity entity = source.getEntity();
            if (entity == null) {
                return null;
            }
            return source.withLevel((ServerLevel) entity.level())
                    .withPosition(entity.position())
                    .withRotation(entity.getRotationVector());
        };
    }

    private static ContextModifierCommand.Transformation parsePositionedModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() == 4 && "as".equals(names.get(2)) && "targets".equals(names.get(3))
                && "@s".equals(extractNodeText(context, "targets"))) {
            return (ctx, source) -> source.getEntity() == null
                    ? null
                    : source.withPosition(source.getEntity().position());
        }
        if (names.size() == 3 && "pos".equals(names.get(2))) {
            try {
                Coordinates coordinates = context.getArgument("pos", Coordinates.class);
                return (ctx, source) -> source.withPosition(coordinates.getPosition(source))
                        .withAnchor(EntityAnchorArgument.Anchor.FEET);
            } catch (IllegalArgumentException exception) {
                return null;
            }
        }
        return null;
    }

    private static ContextModifierCommand.Transformation parseRotatedModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() == 4 && "as".equals(names.get(2)) && "targets".equals(names.get(3))
                && "@s".equals(extractNodeText(context, "targets"))) {
            return (ctx, source) -> source.getEntity() == null
                    ? null
                    : source.withRotation(source.getEntity().getRotationVector());
        }
        if (names.size() == 3 && "rot".equals(names.get(2))) {
            try {
                Coordinates coordinates = context.getArgument("rot", Coordinates.class);
                return (ctx, source) -> source.withRotation(coordinates.getRotation(source));
            } catch (IllegalArgumentException exception) {
                return null;
            }
        }
        return null;
    }

    private static ContextModifierCommand.Transformation parseAnchoredModifier(
            CommandContext<CommandSourceStack> context,
            List<String> names
    ) {
        if (names.size() != 3 || !"anchor".equals(names.get(2))) {
            return null;
        }
        try {
            EntityAnchorArgument.Anchor anchor =
                    context.getArgument("anchor", EntityAnchorArgument.Anchor.class);
            return (ctx, source) -> source.withAnchor(anchor);
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private static ParsedCondition parseScoreCondition(
            CommandContext<CommandSourceStack> context
    ) {
        List<String> names = nodeNames(context);
        if (names.size() < 7
                || !"execute".equals(names.get(0))
                || (!"if".equals(names.get(1)) && !"unless".equals(names.get(1)))
                || !"score".equals(names.get(2))
                || !"target".equals(names.get(3))
                || !"targetObjective".equals(names.get(4))) {
            return null;
        }

        ScoreHolderArgument.Result targetResult;
        String targetObjective;
        try {
            targetResult = context.getArgument("target", ScoreHolderArgument.Result.class);
            targetObjective = context.getArgument("targetObjective", String.class);
        } catch (IllegalArgumentException exception) {
            return null;
        }

        String targetText = extractNodeText(context, "target");
        boolean isTargetSelf = "@s".equals(targetText);
        ScoreHolder targetHolder = isTargetSelf
                ? null
                : resolveStaticHolder(targetResult, context.getSource(), extractNodeText(context, "targets"));
        if (!isTargetSelf && targetHolder == null) {
            return null;
        }

        ParsedTarget target = new ParsedTarget(
                targetHolder, isTargetSelf, targetObjective, "unless".equals(names.get(1))
        );
        if (names.size() == 7 && "matches".equals(names.get(5)) && "range".equals(names.get(6))) {
            return parseRangeCondition(context, target);
        }
        return parseBinaryCondition(context, names, target);
    }

    private static ParsedCondition parseRangeCondition(
            CommandContext<CommandSourceStack> context,
            ParsedTarget target
    ) {
        try {
            MinMaxBounds.Ints range = context.getArgument("range", MinMaxBounds.Ints.class);
            return new ParsedCondition(
                    target.holder(), target.isSelf(), target.objective(),
                    null, null, false, null, range, target.unless()
            );
        } catch (IllegalArgumentException exception) {
            return null;
        }
    }

    private static ParsedCondition parseBinaryCondition(
            CommandContext<CommandSourceStack> context,
            List<String> names,
            ParsedTarget target
    ) {
        if (names.size() != 8 || !"source".equals(names.get(6)) || !"sourceObjective".equals(names.get(7))) {
            return null;
        }
        ScoreConditionCommand.Operator operator = parseOperator(names.get(5));
        if (operator == null) {
            return null;
        }

        ScoreHolderArgument.Result sourceResult;
        String sourceObjective;
        try {
            sourceResult = context.getArgument("source", ScoreHolderArgument.Result.class);
            sourceObjective = context.getArgument("sourceObjective", String.class);
        } catch (IllegalArgumentException exception) {
            return null;
        }

        String sourceText = extractNodeText(context, "source");
        boolean isSourceSelf = "@s".equals(sourceText);
        ScoreHolder sourceHolder = isSourceSelf
                ? null
                : resolveStaticHolder(sourceResult, context.getSource(), extractNodeText(context, "source"));
        if (!isSourceSelf && sourceHolder == null) {
            return null;
        }

        return new ParsedCondition(
                target.holder(), target.isSelf(), target.objective(),
                operator, sourceHolder, isSourceSelf, sourceObjective, null, target.unless()
        );
    }

    private static final java.util.Map<String, ScoreConditionCommand.Operator> OPERATORS =
            java.util.Map.of(
                    "=", ScoreConditionCommand.Operator.EQUALS,
                    "<", ScoreConditionCommand.Operator.LESS_THAN,
                    "<=", ScoreConditionCommand.Operator.LESS_THAN_OR_EQUAL,
                    ">", ScoreConditionCommand.Operator.GREATER_THAN,
                    ">=", ScoreConditionCommand.Operator.GREATER_THAN_OR_EQUAL
            );

    private static ScoreConditionCommand.Operator parseOperator(String text) {
        return OPERATORS.get(text);
    }

    private static ParsedStore parseScoreStore(
            CommandContext<CommandSourceStack> context
    ) {
        List<String> names = nodeNames(context);
        if (names.size() != 6
                || !"execute".equals(names.get(0))
                || !"store".equals(names.get(1))
                || (!"result".equals(names.get(2)) && !"success".equals(names.get(2)))
                || !"score".equals(names.get(3))
                || !"targets".equals(names.get(4))
                || !"objective".equals(names.get(5))) {
            return null;
        }

        ScoreHolderArgument.Result targetsResult;
        String objective;
        try {
            targetsResult = context.getArgument("targets", ScoreHolderArgument.Result.class);
            objective = context.getArgument("objective", String.class);
        } catch (IllegalArgumentException exception) {
            return null;
        }

        String targetText = extractNodeText(context, "targets");
        boolean isTargetSelf = "@s".equals(targetText);
        ScoreHolder targetHolder = isTargetSelf
                ? null
                : resolveStaticHolder(targetsResult, context.getSource(), extractNodeText(context, "targets"));
        if (!isTargetSelf && targetHolder == null) {
            return null;
        }

        return new ParsedStore(targetHolder, isTargetSelf, objective, "result".equals(names.get(2)));
    }

    private record ParsedCondition(
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            String targetObjective,
            ScoreConditionCommand.Operator operator,
            ScoreHolder sourceHolder,
            boolean isSourceSelf,
            String sourceObjective,
            MinMaxBounds.Ints range,
            boolean unless
    ) {
    }

    private record ParsedStore(
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            String objective,
            boolean isResult
    ) {
    }

    private record ParsedTarget(
            ScoreHolder holder,
            boolean isSelf,
            String objective,
            boolean unless
    ) {
    }

    private static boolean compileScoreAdd(
            CommandContext<CommandSourceStack> context,
            Identifier functionId
    ) {
        ScoreAddCommand.Operation operation = parseOperation(context);
        if (operation == null) {
            return false;
        }

        ScoreHolderArgument.Result targetResult;
        int amount;
        try {
            targetResult = context.getArgument("targets", ScoreHolderArgument.Result.class);
            context.getArgument("objective", String.class);
            amount = context.getArgument("score", Integer.class);
        } catch (IllegalArgumentException exception) {
            return false;
        }

        String targetText = extractNodeText(context, "targets");
        boolean isSelfSelector = "@s".equals(targetText);
        ScoreHolder holder = null;
        if (!isSelfSelector) {
            holder = resolveStaticHolder(targetResult, context.getSource(), targetText);
            if (holder == null) {
                return false;
            }
        }

        CommandContextAccessor<CommandSourceStack> accessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) context;
        accessor.functionCompiler$setCommand(
                new ScoreAddCommand(context.getCommand(), holder, isSelfSelector, operation, amount, functionId)
        );
        ProbeMetrics.scoreAddCompiled(functionId);
        return true;
    }

    private static boolean compileScoreReset(
            CommandContext<CommandSourceStack> context,
            Identifier functionId
    ) {
        List<String> names = nodeNames(context);
        boolean hasObjective = names.size() == 5;
        if ((names.size() != 4 && names.size() != 5)
                || !"scoreboard".equals(names.get(0))
                || !"players".equals(names.get(1))
                || !"reset".equals(names.get(2))
                || !"targets".equals(names.get(3))
                || (hasObjective && !"objective".equals(names.get(4)))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        if (!command.getClass().isSynthetic()
                || command.getClass().getNestHost() != ScoreboardCommand.class) {
            return false;
        }

        ScoreHolderArgument.Result targetsResult;
        try {
            targetsResult = context.getArgument("targets", ScoreHolderArgument.Result.class);
            if (hasObjective) {
                context.getArgument("objective", String.class);
            }
        } catch (IllegalArgumentException exception) {
            return false;
        }

        String targetText = extractNodeText(context, "targets");
        boolean isTargetSelf = "@s".equals(targetText);
        ScoreHolder targetHolder = isTargetSelf
                ? null
                : resolveStaticHolder(targetsResult, context.getSource(), extractNodeText(context, "targets"));
        if (!isTargetSelf && targetHolder == null) {
            return false;
        }

        CommandContextAccessor<CommandSourceStack> accessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) context;
        accessor.functionCompiler$setCommand(
                new ScoreResetCommand(
                        command,
                        targetHolder,
                        isTargetSelf,
                        hasObjective,
                        functionId
                )
        );
        ProbeMetrics.scoreAddCompiled(functionId);
        return true;
    }

    private static boolean compileScoreOperation(
            CommandContext<CommandSourceStack> context,
            Identifier functionId
    ) {
        List<String> names = nodeNames(context);
        if (names.size() != 8
                || !"scoreboard".equals(names.get(0))
                || !"players".equals(names.get(1))
                || !"operation".equals(names.get(2))
                || !"targets".equals(names.get(3))
                || !"targetObjective".equals(names.get(4))
                || !"operation".equals(names.get(5))
                || !"source".equals(names.get(6))
                || !"sourceObjective".equals(names.get(7))) {
            return false;
        }
        Command<CommandSourceStack> command = context.getCommand();
        if (!command.getClass().isSynthetic()
                || command.getClass().getNestHost() != ScoreboardCommand.class) {
            return false;
        }

        ScoreHolderArgument.Result targetsResult;
        OperationArgument.Operation operation;
        ScoreHolderArgument.Result sourceResult;
        try {
            targetsResult = context.getArgument("targets", ScoreHolderArgument.Result.class);
            context.getArgument("targetObjective", String.class);
            operation = context.getArgument("operation", OperationArgument.Operation.class);
            sourceResult = context.getArgument("source", ScoreHolderArgument.Result.class);
            context.getArgument("sourceObjective", String.class);
        } catch (IllegalArgumentException exception) {
            return false;
        }

        String targetText = extractNodeText(context, "targets");
        boolean isTargetSelf = "@s".equals(targetText);
        ScoreHolder targetHolder = isTargetSelf
                ? null
                : resolveStaticHolder(targetsResult, context.getSource(), extractNodeText(context, "targets"));

        String sourceText = extractNodeText(context, "source");
        boolean isSourceSelf = "@s".equals(sourceText);
        ScoreHolder sourceHolder = isSourceSelf
                ? null
                : resolveStaticHolder(sourceResult, context.getSource(), extractNodeText(context, "source"));

        if ((!isTargetSelf && targetHolder == null) || (!isSourceSelf && sourceHolder == null)) {
            return false;
        }

        CommandContextAccessor<CommandSourceStack> accessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) context;
        accessor.functionCompiler$setCommand(
                new ScoreOperationCommand(
                        command,
                        targetHolder,
                        isTargetSelf,
                        operation,
                        sourceHolder,
                        isSourceSelf,
                        functionId
                )
        );
        ProbeMetrics.scoreAddCompiled(functionId);
        return true;
    }

    private static ScoreAddCommand.Operation parseOperation(CommandContext<CommandSourceStack> context) {
        List<String> names = nodeNames(context);
        if (names.size() != 6
                || !"scoreboard".equals(names.get(0))
                || !"players".equals(names.get(1))
                || !"targets".equals(names.get(3))
                || !"objective".equals(names.get(4))
                || !"score".equals(names.get(5))) {
            return null;
        }
        Command<CommandSourceStack> command = context.getCommand();
        if (!command.getClass().isSynthetic()
                || command.getClass().getNestHost() != ScoreboardCommand.class) {
            return null;
        }
        return switch (names.get(2)) {
            case "add" -> ScoreAddCommand.Operation.ADD;
            case "set" -> ScoreAddCommand.Operation.SET;
            case "remove" -> ScoreAddCommand.Operation.REMOVE;
            default -> null;
        };
    }

    static String extractNodeText(CommandContext<CommandSourceStack> context, String nodeName) {
        for (var node : context.getNodes()) {
            if (nodeName.equals(node.getNode().getName())) {
                return node.getRange().get(context.getInput());
            }
        }
        return null;
    }

    private static ScoreHolder resolveStaticHolder(
            ScoreHolderArgument.Result targetResult,
            CommandSourceStack source,
            String holderText
    ) {
        // Only literal fake holders (`#...`) are specialized. A literal
        // player-name holder must be declined *before* resolving the name:
        // resolving one consults the server's player list, which is null while
        // a datapack is loading, and that lookup previously threw an NPE that
        // failed the whole function load.
        if (holderText == null || !holderText.startsWith("#")) {
            return null;
        }
        if (targetResult instanceof ScoreHolderArgument.SelectorResult) {
            return null;
        }
        Collection<ScoreHolder> holders;
        try {
            holders = targetResult.getNames(source, List::of);
        } catch (CommandSyntaxException exception) {
            return null;
        }
        if (holders.size() != 1) {
            return null;
        }
        ScoreHolder holder = holders.iterator().next();
        return holder.getScoreboardName().startsWith("#") ? holder : null;
    }

    static List<String> nodeNames(CommandContext<CommandSourceStack> context) {
        return context.getNodes().stream()
                .map(parsed -> parsed.getNode().getName())
                .toList();
    }

    static void applyCommand(
            CommandContext<CommandSourceStack> context,
            Command<CommandSourceStack> compiledCommand,
            Identifier functionId
    ) {
        @SuppressWarnings("unchecked")
        CommandContextAccessor<CommandSourceStack> accessor =
                (CommandContextAccessor<CommandSourceStack>) (Object) context;
        accessor.functionCompiler$setCommand(compiledCommand);
        ProbeMetrics.scoreAddCompiled(functionId);
    }
}
