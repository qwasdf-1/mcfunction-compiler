package dev.functioncompiler;
import com.mojang.brigadier.CommandDispatcher;
import net.minecraft.commands.CommandSourceStack;
/** Production build never includes synthetic commands or scoreboard observers. */
final class CompilerFixtures {
    static final boolean ENABLED = false;
    private CompilerFixtures() {}
    static void register(CommandDispatcher<CommandSourceStack> dispatcher) {}
    static String diagnostics() { return ""; }
}
