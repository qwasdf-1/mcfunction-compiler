package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.context.ContextChain;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.advancements.predicates.MinMaxBounds;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.ExecutionCommandSource;
import net.minecraft.resources.Identifier;
import net.minecraft.server.ServerScoreboard;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.scores.Objective;
import net.minecraft.world.scores.ReadOnlyScoreInfo;
import net.minecraft.world.scores.ScoreHolder;

final class ScoreConditionCommand implements FusableCommand {
    enum Operator {
        EQUALS,
        LESS_THAN,
        LESS_THAN_OR_EQUAL,
        GREATER_THAN,
        GREATER_THAN_OR_EQUAL
    }

    private final ContextChain<CommandSourceStack> fallbackChain;
    private final ScoreHolder targetHolder;
    private final boolean isTargetSelf;
    private final String targetObjective;
    private final Operator operator;
    private final ScoreHolder sourceHolder;
    private final boolean isSourceSelf;
    private final String sourceObjective;
    private final MinMaxBounds.Ints range;
    private final boolean unless;
    private final Command<CommandSourceStack> innerCommand;
    private final Identifier functionId;

    ScoreConditionCommand(
            ContextChain<CommandSourceStack> fallbackChain,
            ScoreHolder targetHolder,
            boolean isTargetSelf,
            String targetObjective,
            Operator operator,
            ScoreHolder sourceHolder,
            boolean isSourceSelf,
            String sourceObjective,
            MinMaxBounds.Ints range,
            boolean unless,
            Command<CommandSourceStack> innerCommand,
            Identifier functionId
    ) {
        this.fallbackChain = fallbackChain;
        this.targetHolder = targetHolder;
        this.isTargetSelf = isTargetSelf;
        this.targetObjective = targetObjective;
        this.operator = operator;
        this.sourceHolder = sourceHolder;
        this.isSourceSelf = isSourceSelf;
        this.sourceObjective = sourceObjective;
        this.range = range;
        this.unless = unless;
        this.innerCommand = innerCommand;
        this.functionId = functionId;
    }

    /**
     * IR-017: one Brigadier-validated literal fake-holder range predicate
     * guarding either an IR mutation or one of the four safe IR binary
     * operations. The source regex is an eligibility preflight, not a command
     * parser: the actual operand identity, operation and bounds come from
     * the existing parsed Minecraft callbacks.
     */
    // IR-017 stays disabled unless explicitly enabled alongside the typed IR.
    // OFF preserves IR-009's exact integer/mutation-only acceptance and gives
    // the real-datapack coverage study an identical-compiler control arm.
    private static final boolean RANGE_GUARDS_ENABLED =
            Boolean.parseBoolean(System.getenv("FC_TYPED_IR_RANGE_GUARDS"));

    private static final String IR_RANGE =
            "(?:-?\\d+(?:\\.\\.(?:-?\\d+)?)?|\\.\\.-?\\d+)";
    private static final String IR_MUTATION =
            "scoreboard players (?:add|set|remove) "
                    + "#[A-Za-z0-9_.+\\-]+ [A-Za-z0-9_.+\\-]+ -?\\d+";
    private static final String IR_BINARY =
            "scoreboard players operation #[A-Za-z0-9_.+\\-]+ "
                    + "[A-Za-z0-9_.+\\-]+ (?:=|\\+=|-=|\\*=) "
                    + "#[A-Za-z0-9_.+\\-]+ [A-Za-z0-9_.+\\-]+";
    private static final java.util.regex.Pattern IR_GUARD =
            java.util.regex.Pattern.compile(
                    "^execute (if|unless) score (#[A-Za-z0-9_.+\\-]+) "
                            + "([A-Za-z0-9_.+\\-]+) matches (" + IR_RANGE + ") "
                            + "run (" + IR_MUTATION + "|" + IR_BINARY + ")$");

    static boolean typedIrLiteralGuardShape(String input) {
        if (input == null) return false;
        var matcher = IR_GUARD.matcher(input);
        if (!matcher.matches()) return false;
        return RANGE_GUARDS_ENABLED
                || (!matcher.group(4).contains("..")
                        && !matcher.group(5).startsWith("scoreboard players operation "));
    }

    /**
     * Do not trust the text representation of a Minecraft range alone: check
     * that the already-parsed MinMaxBounds matches both inclusive endpoints
     * and rejects the immediate values outside any bounded endpoint. MIN/MAX
     * are explicitly tested for open-ended ranges. Overflow is declined.
     */
    static boolean sameParsedRange(MinMaxBounds.Ints parsed, String source) {
        if (parsed == null || source == null) return false;
        try {
            int separator = source.indexOf("..");
            int lower;
            int upper;
            if (separator < 0) {
                lower = Integer.parseInt(source);
                upper = lower;
            } else {
                String left = source.substring(0, separator);
                String right = source.substring(separator + 2);
                if (left.isEmpty() && right.isEmpty()) return false;
                lower = left.isEmpty() ? Integer.MIN_VALUE : Integer.parseInt(left);
                upper = right.isEmpty() ? Integer.MAX_VALUE : Integer.parseInt(right);
            }
            if (lower > upper || !parsed.matches(lower) || !parsed.matches(upper)) {
                return false;
            }
            if (lower != Integer.MIN_VALUE && parsed.matches(lower - 1)) return false;
            if (upper != Integer.MAX_VALUE && parsed.matches(upper + 1)) return false;
            return true;
        } catch (NumberFormatException | IndexOutOfBoundsException invalid) {
            return false;
        }
    }

    TypedScoreIR.Conditional toTypedIR(FusedRegionPrototype.FusedCommand parsed) {
        if (isTargetSelf || targetHolder == null || range == null
                || operator != null || sourceHolder != null
                || targetObjective == null) {
            return null;
        }
        var matcher = IR_GUARD.matcher(parsed.commandInput());
        if (!matcher.matches()
                || (!RANGE_GUARDS_ENABLED
                        && (matcher.group(4).contains("..")
                                || innerCommand instanceof ScoreOperationCommand))
                || !matcher.group(2).equals(targetHolder.getScoreboardName())
                || !matcher.group(3).equals(targetObjective)
                || ("unless".equals(matcher.group(1)) != unless)
                || !sameParsedRange(range, matcher.group(4))) {
            return null;
        }
        TypedScoreIR.Instruction terminal = null;
        if (innerCommand instanceof ScoreAddCommand score) {
            terminal = score.toMutation(parsed, matcher.group(5));
        } else if (innerCommand instanceof ScoreOperationCommand binary) {
            terminal = binary.toBinary(parsed, matcher.group(5));
        }
        return terminal == null ? null : new TypedScoreIR.Conditional(
                parsed, terminal, targetHolder, targetObjective, range, unless);
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
        // The fallback bypasses the execution queue, so it must only run when
        // nothing that motivated the compile is active; a timing-only or
        // bytecode-only arm still needs the compiled (quota-exact) path.
        if (!ProbeConfiguration.scoreAddPrototypeEnabled()
                && !ProbeConfiguration.scoreAddTimingEnabled()
                && !ProbeConfiguration.fusedRegionPrototypeEnabled()
                && !ProbeConfiguration.bytecodeRegionPrototypeEnabled()) {
            return fallbackChain.executeAll(
                    context.getSource(),
                    ExecutionCommandSource.resultConsumer()
            );
        }

        CommandSourceStack source = context.getSource();
        if (hasMissingObjectiveOrHolder(source)) {
            return fallbackChain.executeAll(source, ExecutionCommandSource.resultConsumer());
        }

        boolean matched = isConditionMet(source);
        if (unless == matched) {
            return 0;
        }

        // Vanilla charges one quota debit for the condition stage (a redirect
        // modifier) in BuildContexts — but only resolves sources through it,
        // so a failed condition queues no per-source ExecuteCommand and costs
        // exactly the stage debit. The compiled chain always pays the
        // per-source debit (the entry queues an ExecuteCommand for this
        // command), so the stage debit is charged here, only on a passing
        // condition, keeping the per-line totals equal in both cases. The
        // inner command then runs only while the remaining quota has not gone
        // negative — the compiled form of vanilla stopping the queue before
        // this line's ExecuteCommand.
        ExecutionContextBridge.chargeInlinedModifierStages(1);
        if (!ExecutionContextBridge.inlinedInnerRunnable()) {
            return 0;
        }

        int result = innerCommand.run(context);
        if (ProbeConfiguration.scoreAddMetricsEnabled()) {
            ProbeMetrics.scoreAddExecuted(functionId);
        }
        return result;
    }

    private boolean hasMissingObjectiveOrHolder(CommandSourceStack source) {
        ScoreHolder target = resolveHolder(source, isTargetSelf, targetHolder);
        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        if (target == null || scoreboard.getObjective(targetObjective) == null) {
            return true;
        }
        if (range == null) {
            ScoreHolder src = resolveHolder(source, isSourceSelf, sourceHolder);
            return src == null || scoreboard.getObjective(sourceObjective) == null;
        }
        return false;
    }

    private boolean isConditionMet(CommandSourceStack source) {
        ScoreHolder target = resolveHolder(source, isTargetSelf, targetHolder);
        ServerScoreboard scoreboard = source.getServer().getScoreboard();
        Objective targetObj = scoreboard.getObjective(targetObjective);
        ReadOnlyScoreInfo targetInfo = scoreboard.getPlayerScoreInfo(target, targetObj);
        if (targetInfo == null) {
            return false;
        }

        if (range != null) {
            return range.matches(targetInfo.value());
        }

        ScoreHolder src = resolveHolder(source, isSourceSelf, sourceHolder);
        Objective sourceObj = scoreboard.getObjective(sourceObjective);
        ReadOnlyScoreInfo sourceInfo = scoreboard.getPlayerScoreInfo(src, sourceObj);
        return sourceInfo != null && compareScores(targetInfo.value(), sourceInfo.value(), operator);
    }

    private static ScoreHolder resolveHolder(
            CommandSourceStack source,
            boolean isSelf,
            ScoreHolder staticHolder
    ) {
        if (isSelf) {
            Entity entity = source.getEntity();
            return entity != null ? entity : null;
        }
        return staticHolder;
    }

    private static boolean compareScores(int target, int source, Operator op) {
        return switch (op) {
            case EQUALS -> target == source;
            case LESS_THAN -> target < source;
            case LESS_THAN_OR_EQUAL -> target <= source;
            case GREATER_THAN -> target > source;
            case GREATER_THAN_OR_EQUAL -> target >= source;
        };
    }
}
