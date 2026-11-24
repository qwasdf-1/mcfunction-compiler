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
        // IR-only mode is intentionally narrower than ScoreAddPrototype's
        // legacy parser. The legacy parser mutates Brigadier contexts while
        // rewriting "execute" chains; if TypedScoreIR subsequently rejects
        // the command, the saved fallback can reference the mutated wrapper
        // recursively (observed on real Vein Miner 5.3.0 at startup).
        //
        // Before *any* parser mutation, leave every unsupported source shape
        // on its original BuildContexts/vanilla scheduler path. This is
        // admission control, NOT text parsing: accepted candidates still
        // pass the ordinary Brigadier and typed-IR argument verification.
        boolean typedOnly = TypedScoreIR.enabledFor(functionId)
                && !ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.scoreAddTimingEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()
                && !ProbeConfiguration.bytecodeRegionPrototypeEnabled();
        if (typedOnly) {
            String input = ((BuildContextsAccessor<CommandSourceStack>) buildContexts)
                    .functionCompiler$getCommandInput();
            boolean acceptedShape = chain.getStage() == ContextChain.Stage.EXECUTE
                    ? ScoreAddCommand.typedIrLiteralSourceShape(input)
                            || ScoreOperationCommand.typedIrLiteralSourceShape(input)
                    : ScoreConditionCommand.typedIrLiteralGuardShape(input)
                        && !ScoreOperationCommand.exceptionalSourceShape(input);
            if (!acceptedShape) return;
        }

        if (chain.getStage() != ContextChain.Stage.EXECUTE) {
            compileChainedModifiers(buildContexts, chain, functionId);
            return;
        }

        CommandContext<CommandSourceStack> context = chain.getTopContext();
        boolean audit = CompilerAcceptanceAudit.enabledFor(functionId);
        Command<CommandSourceStack> before = audit ? context.getCommand() : null;
        try {
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
        } finally {
            if (audit) {
                CompilerAcceptanceAudit.record(functionId,
                        context.getCommand() == before ? "bare_declined" : "bare_terminal_installed",
                        context.getInput());
            }
        }
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
            CompilerAcceptanceAudit.record(functionId, "chain_missing_parts",
                    chain.getTopContext().getInput());
            return;
        }

        // Snapshot the real Brigadier terminal BEFORE a prototype replaces
        // the live parsed callback. For typed-only guarded commands, the
        // original parsed fallback must not share the mutated executable
        // context: that would recursively call ScoreConditionCommand again
        // when @s (or a runtime objective) is unavailable.
        Command<CommandSourceStack> originalExecutableCommand = executable.getCommand();
        if (!compileExecutable(executable, functionId)) {
            CompilerAcceptanceAudit.record(functionId, "chain_executable_declined",
                    chain.getTopContext().getInput());
            return;
        }

        // Correct the historical literal target-node lookup only when the
        // *whole* source line has the exact IR-009 guard/terminal shape.
        // Unsupported modifiers must stay on their existing vanilla path.
        boolean typedLiteralGuard = TypedScoreIR.enabledFor(functionId)
                && ScoreConditionCommand.typedIrLiteralGuardShape(
                        ((BuildContextsAccessor<CommandSourceStack>) buildContexts)
                                .functionCompiler$getCommandInput());
        List<Object> parsedModifiers = parseModifiers(modifiers, typedLiteralGuard);
        if (parsedModifiers == null) {
            // The terminal callback may have been replaced already even though
            // vanilla must continue to interpret the surrounding modifiers.
            CompilerAcceptanceAudit.record(functionId, "chain_terminal_only",
                    chain.getTopContext().getInput());
            return;
        }

        ContextChain<CommandSourceStack> nativeFallback = chain;
        boolean typedOnly = TypedScoreIR.enabledFor(functionId)
                && !ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.scoreAddTimingEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()
                && !ProbeConfiguration.bytecodeRegionPrototypeEnabled();
        if (typedOnly && typedLiteralGuard) {
            // Brigadier CommandContext is mutable through our mixin. Clone
            // ONLY the terminal with its original vanilla callback, leaving
            // modifier contexts and their parsed selector/range arguments
            // untouched. This is the genuine original command for error and
            // objective-lifecycle fallback, not a reparse or emulation.
            CommandContext<CommandSourceStack> originalExecutable =
                    new CommandContext<>(
                            executable.getSource(),
                            executable.getInput(),
                            ((CommandContextAccessor<CommandSourceStack>) (Object) executable)
                                    .functionCompiler$getArguments(),
                            originalExecutableCommand,
                            executable.getRootNode(),
                            executable.getNodes(),
                            executable.getRange(),
                            executable.getChild(),
                            executable.getRedirectModifier(),
                            executable.isForked()
                    );
            nativeFallback = new ContextChain<>(List.copyOf(modifiers), originalExecutable);
        }
        Command<CommandSourceStack> wrapped = wrapModifiers(
                nativeFallback, parsedModifiers, executable.getCommand(), functionId
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
        CompilerAcceptanceAudit.record(functionId, "chain_fully_lowered",
                chain.getTopContext().getInput());
    }

    /**
     * IR-039: inspect the ORIGINAL Brigadier chain without rewriting it.
     * Only a detached terminal context is wrapped for the existing typed
     * terminal validator. Declined candidates and fallback retain the native
     * BuildContexts action and all of its original redirect callbacks.
     */
    @SuppressWarnings("unchecked")
    static TypedScoreIR.Compound lowerCompound(
            UnboundEntryAction<CommandSourceStack> entry, Identifier functionId) {
        if (!CompoundScoreIR.enabled() || !(entry instanceof BuildContexts.Unbound<?> unbound)) return null;
        // Do not compose with a legacy callback-rewriting prototype.
        if (ProbeConfiguration.scoreAddPrototypeEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()
                || ProbeConfiguration.fusedRegionPrototypeEnabled()
                || ProbeConfiguration.bytecodeRegionPrototypeEnabled()) return null;
        var accessor = (BuildContextsAccessor<CommandSourceStack>) unbound;
        String input = accessor.functionCompiler$getCommandInput();
        if (input == null || !input.startsWith("execute ")) return null;
        String[] halves = input.substring(8).split(" run ", -1);
        if (halves.length != 2) return null;
        String[] parts = halves[0].split(" (?=(?:if|unless) score )", -1);
        if (parts.length < 2 || parts.length > CompoundScoreIR.MAX_PREDICATES) return null;
        for (String part : parts) {
            if (!ScoreConditionCommand.typedIrLiteralGuardShape(
                    "execute " + part + " run " + halves[1])) return null;
        }

        ContextChain<CommandSourceStack> chain = accessor.functionCompiler$getCommand();
        if (chain.getStage() == ContextChain.Stage.EXECUTE) return null;
        var chainAccessor = (ContextChainAccessor<CommandSourceStack>) (Object) chain;
        List<CompoundScoreIR.Predicate> predicates = new ArrayList<>();
        for (CommandContext<CommandSourceStack> modifier : chainAccessor.functionCompiler$getModifiers()) {
            if (nodeNames(modifier).equals(List.of("run"))) continue;
            if (predicates.size() >= parts.length || modifier.getRedirectModifier() == null) return null;
            // Source text is ONLY an eligibility and identity check. Actual
            // holders, objectives, comparisons and ranges come from Brigadier.
            ParsedCondition parsed = parseScoreCondition(modifier, true, true);
            if (parsed == null) return null;
            String[] words = parts[predicates.size()].split(" ");
            if (parsed.unless() != "unless".equals(words[0])
                    || !words[2].equals(TypedScoreIR.slotName(parsed.targetHolder(), parsed.isTargetSelf()))
                    || !words[3].equals(parsed.targetObjective())) return null;
            CompoundScoreIR.Operand left = new CompoundScoreIR.Operand(
                    parsed.targetHolder(), parsed.isTargetSelf(), parsed.targetObjective());
            if ("matches".equals(words[4])) {
                if (words.length != 6 || parsed.operator() != null
                        || !ScoreConditionCommand.sameParsedRange(parsed.range(), words[5])) return null;
                predicates.add(new CompoundScoreIR.Predicate(
                        left, parsed.range(), words[5], null, null, parsed.unless()));
            } else {
                if (words.length != 7 || parsed.range() != null
                        || parsed.operator() != parseOperator(words[4])
                        || !words[5].equals(TypedScoreIR.slotName(parsed.sourceHolder(), parsed.isSourceSelf()))
                        || !words[6].equals(parsed.sourceObjective())) return null;
                var right = new CompoundScoreIR.Operand(
                        parsed.sourceHolder(), parsed.isSourceSelf(), parsed.sourceObjective());
                predicates.add(new CompoundScoreIR.Predicate(
                        left, null, null, parsed.operator(), right, parsed.unless()));
            }
        }
        if (predicates.size() != parts.length) return null;
        var executable = chainAccessor.functionCompiler$getExecutable();
        if (executable == null || executable.isForked()) return null;
        var copy = new CommandContext<>(executable.getSource(), executable.getInput(),
                ((CommandContextAccessor<CommandSourceStack>) (Object) executable)
                        .functionCompiler$getArguments(),
                executable.getCommand(), executable.getRootNode(), executable.getNodes(),
                executable.getRange(), executable.getChild(), executable.getRedirectModifier(),
                executable.isForked());
        if (!compileScoreAdd(copy, functionId) && !compileScoreOperation(copy, functionId)) return null;
        var original = new FusedRegionPrototype.FusedCommand(
                entry, new ContextChain<>(List.of(), copy), input);
        TypedScoreIR.Instruction terminal = null;
        if (copy.getCommand() instanceof ScoreAddCommand mutation)
            terminal = mutation.toMutation(original, halves[1]);
        else if (copy.getCommand() instanceof ScoreOperationCommand binary)
            terminal = binary.toBinary(original, halves[1]);
        return terminal == null ? null : new TypedScoreIR.Compound(original, terminal, predicates,
                CompoundScoreIR.dataflowEnabledFor(functionId));
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

    private static List<Object> parseModifiers(
            List<CommandContext<CommandSourceStack>> modifiers,
            boolean typedLiteralGuard
    ) {
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
            Object parsed = parseSingleModifier(mod, typedLiteralGuard);
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

    private static Object parseSingleModifier(
            CommandContext<CommandSourceStack> mod, boolean typedLiteralGuard
    ) {
        // Only IR-009's exact literal guard shape is allowed to correct the
        // historical target/targets lookup, preventing an otherwise declined
        // nonliteral / ranged condition from being silently rewritten.
        if (typedLiteralGuard) {
            Object guarded = parseScoreCondition(mod, true);
            if (guarded != null) return guarded;
        }
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
        return parseScoreCondition(context, false);
    }

    private static ParsedCondition parseScoreCondition(
            CommandContext<CommandSourceStack> context, boolean typedIrTargetFix
    ) {
        return parseScoreCondition(context, typedIrTargetFix, false);
    }

    private static ParsedCondition parseScoreCondition(
            CommandContext<CommandSourceStack> context, boolean typedIrTargetFix,
            boolean compound
    ) {
        List<String> names = nodeNames(context);
        // A redirected execute context can begin directly with if/unless.
        // Normalize only within the immutable IR-039 candidate parser.
        if (compound && !names.isEmpty()
                && ("if".equals(names.getFirst()) || "unless".equals(names.getFirst()))) {
            List<String> normalized = new ArrayList<>();
            normalized.add("execute");
            normalized.addAll(names);
            names = normalized;
        }
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
                : resolveStaticHolder(targetResult, context.getSource(),
                        typedIrTargetFix ? targetText : extractNodeText(context, "targets"));
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
        String objectiveName;
        int amount;
        try {
            targetResult = context.getArgument("targets", ScoreHolderArgument.Result.class);
            objectiveName = context.getArgument("objective", String.class);
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
                new ScoreAddCommand(context.getCommand(), holder, isSelfSelector, operation, amount,
                        functionId, objectiveName)
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
