package dev.functioncompiler;

import com.mojang.brigadier.Command;
import net.minecraft.commands.CommandSourceStack;

/**
 * Marker interface for specialized commands that can participate in fused regions.
 */
public interface FusableCommand extends Command<CommandSourceStack> {
}
