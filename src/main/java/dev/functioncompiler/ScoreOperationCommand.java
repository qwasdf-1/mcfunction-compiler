package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import dev.functioncompiler.mixin.ScoreboardCommandAccessor;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.ObjectiveArgument;
import net.minecraft.commands.arguments.OperationArgument;
import net.minecraft.resources.Identifier;
import net.minecraft.server.commands.CommandResponseTracker;
import net.minecraft.server.commands.CommandResponseTracker.ElementType;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ScoreAccess;
import net.minecraft.world.scores.ScoreHolder;
import net.minecraft.world.scores.Scoreboard;

final class ScoreOperationCommand implements FusableCommand {
    private final Command<CommandSourceStack> vanillaCommand;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final OperationArgument.Operation operation;
    private final ScoreHolder sourceHolder;
    private final boolean isSourceSelf;
    private final Identifier functionId;

    ScoreOperationCommand(
            Command<CommandSourceStack> vanillaCommand,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            OperationArgument.Operation operation,
            ScoreHolder sourceHolder,
            boolean isSourceSelf,
            Identifier functionId
    ) {
        this.vanillaCommand = vanillaCommand;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.operation = operation;
        this.sourceHolder = sourceHolder;
        this.isSourceSelf = isSourceSelf;
        this.functionId = functionId;
    }

    /**
     * IR-009: restrict to exact literal holders and four single-target
     * scoreboard operations with no exceptions/second writes. The actual
     * operation was already validated by Brigadier and ScoreAddPrototype;
     * this additional text/argument equality check is an eligibility gate.
     */
    private static final boolean ARITHMETIC =
            TypedCompilerConfiguration.flag("FC_TYPED_IR_ARITHMETIC");
    static boolean exceptionalSourceShape(String input) {
        return input != null && (input.contains(" /= ") || input.contains(" %= ") || input.contains(" >< "));
    }

    private static final java.util.regex.Pattern IR_LITERAL_BINARY_SOURCE =
            java.util.regex.Pattern.compile(
                    "^scoreboard players operation (?:#[A-Za-z0-9_.+\\-]+|@s) "
                            + "[A-Za-z0-9_.+\\-]+ (=|\\+=|-=|\\*=|<|>|/=|%=|><) "
                            + "(?:#[A-Za-z0-9_.+\\-]+|@s) [A-Za-z0-9_.+\\-]+$");

    // Preflight only: accepted commands still require their existing
    // Brigadier-validated callback and the strict argument equality below.
    static boolean typedIrLiteralSourceShape(String source) {
        return source != null && IR_LITERAL_BINARY_SOURCE.matcher(source).matches()
                && (TypedScoreIR.selfHolderEnabled() || !source.contains("@s"))
                && (ARITHMETIC || !exceptionalSourceShape(source))
                && (TypedScoreIR.extendedScoreEnabled()
                        || (!source.contains(" < ") && !source.contains(" > ")));
    }

    TypedScoreIR.Binary toTypedIR(FusedRegionPrototype.FusedCommand parsed) {
        return toBinary(parsed, parsed.commandInput());
    }

    /**
     * IR-017: the same strict parsed-terminal lowering may be used beneath
     * a separately validated `execute if/unless score ... matches <range>`.
     * 'parsed' is the parent source's original action, so the callback still
     * has an exact vanilla fallback and trace identity.
     */
    TypedScoreIR.Binary toBinary(FusedRegionPrototype.FusedCommand parsed, String input) {
        if ((!TypedScoreIR.selfHolderEnabled() && (isTargetSelf || isSourceSelf))
                || (!isTargetSelf && targetHolder == null)
                || (!isSourceSelf && sourceHolder == null)) {
            return null;
        }
        String[] words = input.split(" ", -1);
        if (words.length != 8
                || !"scoreboard".equals(words[0])
                || !"players".equals(words[1])
                || !"operation".equals(words[2])
                || !words[3].equals(isTargetSelf ? "@s" : targetHolder.getScoreboardName())
                || !words[6].equals(isSourceSelf ? "@s" : sourceHolder.getScoreboardName())
                || (!isTargetSelf && !words[3].startsWith("#"))
                || (!isSourceSelf && !words[6].startsWith("#"))
                || !words[4].matches("[A-Za-z0-9_.+\\-]+")
                || !words[7].matches("[A-Za-z0-9_.+\\-]+")) {
            return null;
        }
        TypedScoreIR.BinaryOperator op = switch (words[5]) {
            case "=" -> TypedScoreIR.BinaryOperator.ASSIGN;
            case "+=" -> TypedScoreIR.BinaryOperator.ADD;
            case "-=" -> TypedScoreIR.BinaryOperator.SUBTRACT;
            case "*=" -> TypedScoreIR.BinaryOperator.MULTIPLY;
            case "<" -> TypedScoreIR.extendedScoreEnabled()
                    ? TypedScoreIR.BinaryOperator.MINIMUM : null;
            case ">" -> TypedScoreIR.extendedScoreEnabled()
                    ? TypedScoreIR.BinaryOperator.MAXIMUM : null;
            case "/=" -> ARITHMETIC ? TypedScoreIR.BinaryOperator.DIVIDE : null;
            case "%=" -> ARITHMETIC ? TypedScoreIR.BinaryOperator.MODULO : null;
            case "><" -> ARITHMETIC ? TypedScoreIR.BinaryOperator.SWAP : null;
            default -> null; // Unsupported operation stays native.
        };
        if (op == null) return null;
        try {
            var args = parsed.command().getTopContext();
            if (!words[4].equals(args.getArgument("targetObjective", String.class))
                    || !words[7].equals(args.getArgument("sourceObjective", String.class))) {
                return null;
            }
        } catch (IllegalArgumentException invalid) {
            return null;
        }
        return new TypedScoreIR.Binary(
                parsed, targetHolder, isTargetSelf, words[4], op,
                sourceHolder, isSourceSelf, words[7],
                op.nativeArithmetic() ? operation : null
        );
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context) throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddTimingEnabled()) {
            long started = System.nanoTime();
            try {
                return runUntimed(context);
            } finally {
                ProbeMetrics.scoreAddTimed(functionId, System.nanoTime() - started);
            }
        }
        return runUntimed(context);
    }

    private int runUntimed(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()) {
            return vanillaCommand.run(context);
        }

        CommandSourceStack source = context.getSource();
        ScoreHolder target;
        if (isTargetSelf) {
            Entity entity = source.getEntity();
            if (entity == null) {
                return vanillaCommand.run(context);
            }
            target = entity;
        } else {
            target = this.targetHolder;
        }

        ScoreHolder src;
        if (isSourceSelf) {
            Entity entity = source.getEntity();
            if (entity == null) {
                return vanillaCommand.run(context);
            }
            src = entity;
        } else {
            src = this.sourceHolder;
        }

        Objective targetObj = ObjectiveArgument.getWritableObjective(context, "targetObjective");
        Objective sourceObj = ObjectiveArgument.getObjective(context, "sourceObjective");
        Scoreboard scoreboard = source.getServer().getScoreboard();
        ScoreAccess targetScore = scoreboard.getOrCreatePlayerScore(target, targetObj);
        ScoreAccess sourceScore = scoreboard.getOrCreatePlayerScore(src, sourceObj);

        operation.apply(targetScore, sourceScore);

        CommandResponseTracker<ScoreHolder> response = CommandResponseTracker.create();
        response.track(target, targetScore.get());
        int result = response.sendFeedback(
                source,
                true,
                ElementType.ANY,
                ScoreboardCommandAccessor.functionCompiler$getScoreOperationResponse(),
                targetObj
        );
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }
}
