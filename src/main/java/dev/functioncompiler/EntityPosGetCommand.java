package dev.functioncompiler;

import com.mojang.brigadier.Command;
import com.mojang.brigadier.context.CommandContext;
import com.mojang.brigadier.exceptions.CommandSyntaxException;
import net.minecraft.commands.CommandSourceStack;
import net.minecraft.commands.arguments.EntityArgument;
import net.minecraft.commands.arguments.NbtPathArgument;
import net.minecraft.nbt.DoubleTag;
import net.minecraft.nbt.NumericTag;
import net.minecraft.nbt.Tag;
import net.minecraft.server.commands.data.DataCommands;
import net.minecraft.server.commands.data.EntityDataAccessor;
import net.minecraft.util.Mth;
import net.minecraft.world.entity.Entity;
import net.minecraft.world.entity.Marker;
import net.minecraft.world.phys.Vec3;

/**
 * IR-030 research-only terminal specialization for the exact three
 * vm:queue/append_here entity Pos reads.
 *
 * The native execute-store modifier and its callback are deliberately not
 * lowered. This command returns the same integer and uses the same data-get
 * feedback component. It declines to native for passengers, non-Marker
 * entities, non-finite positions, or when other ScoreAdd instrumentation is
 * active. FC_IR030_POS_GET is false by default and the function allowlist is
 * mandatory.
 */
final class EntityPosGetCommand implements FusableCommand {
    private final Command<CommandSourceStack> fallback;
    private final NbtPathArgument.NbtPath path;
    private final int axis;

    EntityPosGetCommand(
            Command<CommandSourceStack> fallback,
            NbtPathArgument.NbtPath path,
            int axis
    ) {
        this.fallback = fallback;
        this.path = path;
        this.axis = axis;
        ProbeMetrics.ir030PosCompiled(axis);
    }

    @Override
    public int run(CommandContext<CommandSourceStack> context)
            throws CommandSyntaxException {
        if (ProbeConfiguration.scoreAddMetricsEnabled()
                || ProbeConfiguration.scoreAddTimingEnabled()) {
            return fallback.run(context);
        }

        // Use the same parsed selector and native single-entity resolution.
        // Let its original CommandSyntaxException propagate unchanged.
        Entity entity;
        try {
            entity = EntityArgument.getEntity(context, "target");
        } catch (CommandSyntaxException exception) {
            if (ProbeConfiguration.ir030PosGetVerify()) {
                ProbeMetrics.ir030PosInvalidTarget();
            }
            throw exception;
        }

        // Entity.saveWithoutId writes vehicle X/Z with passenger Y. The
        // candidate is therefore valid only for an unmounted vanilla Marker.
        if (entity.getVehicle() != null) {
            if (ProbeConfiguration.ir030PosGetVerify()) {
                ProbeMetrics.ir030PosFallbackVehicle();
            }
            return fallback.run(context);
        }
        if (entity.getClass() != Marker.class) {
            if (ProbeConfiguration.ir030PosGetVerify()) {
                ProbeMetrics.ir030PosFallbackEntityType();
            }
            return fallback.run(context);
        }

        Vec3 position = entity.position();
        double value = switch (axis) {
            case 0 -> position.x;
            case 1 -> position.y;
            case 2 -> position.z;
            default -> throw new IllegalStateException("Invalid IR-030 Pos axis " + axis);
        };
        if (!Double.isFinite(value)) {
            if (ProbeConfiguration.ir030PosGetVerify()) {
                ProbeMetrics.ir030PosFallbackNonfinite();
            }
            return fallback.run(context);
        }

        // Native DataCommands.getData uses Mth.floor(NumericTag.doubleValue()).
        int result = Mth.floor(value);
        EntityDataAccessor accessor = new EntityDataAccessor(entity);
        DoubleTag candidateTag = DoubleTag.valueOf(value);

        // Gate C differential mode deliberately pays for the native snapshot
        // so the candidate tag, return value, and feedback component can be
        // compared on the actual live entity. Disable this for later timing.
        if (ProbeConfiguration.ir030PosGetVerify()) {
            Tag nativeTag = DataCommands.getSingleTag(path, accessor);
            if (!(nativeTag instanceof NumericTag numericTag)) {
                ProbeMetrics.ir030PosVerifyMismatch();
                throw new IllegalStateException(
                        "IR-030 native Pos path did not produce a NumericTag: " + nativeTag);
            }
            int nativeResult = Mth.floor(numericTag.doubleValue());
            if (!nativeTag.equals(candidateTag)
                    || nativeResult != result
                    || !accessor.getPrintSuccess(nativeTag)
                            .equals(accessor.getPrintSuccess(candidateTag))) {
                ProbeMetrics.ir030PosVerifyMismatch();
                throw new IllegalStateException(
                        "IR-030 native/candidate Pos mismatch axis=" + axis
                                + " native=" + nativeTag
                                + " candidate=" + candidateTag
                                + " nativeResult=" + nativeResult
                                + " candidateResult=" + result);
            }
            ProbeMetrics.ir030PosVerified();
        }

        context.getSource().sendSuccess(
                () -> accessor.getPrintSuccess(candidateTag), false);
        // No per-callback research counters in genuine uninstrumented CPU
        // arms; diagnostics are exclusive to the native parity verification.
        if (ProbeConfiguration.ir030PosGetVerify()) {
            ProbeMetrics.ir030PosFastPath(axis);
        }
        return result;
    }
}
