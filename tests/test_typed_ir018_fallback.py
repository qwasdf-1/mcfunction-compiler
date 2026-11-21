"""IR-018 regression: original Brigadier callback snapshot avoids recursive fallback.

This is a source contract. The native 87-observation IR-018 five-mode parity
run is the authority for execution, quota and error behavior.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]


class OriginalBrigadierFallback(unittest.TestCase):
    def test_native_terminal_captured_before_legacy_wrapper_mutation(self):
        path=ROOT/"src/main/java/dev/functioncompiler/ScoreAddPrototype.java"
        source=path.read_text()
        self.assertIn(
            "Command<CommandSourceStack> originalExecutableCommand = executable.getCommand();",
            source,
        )
        self.assertIn("CommandContext<CommandSourceStack> originalExecutable =",source)
        self.assertIn("new ContextChain<>(List.copyOf(modifiers), originalExecutable)",source)
        self.assertIn("wrapModifiers(\n                nativeFallback,",source)
        self.assertLess(source.index(
            "Command<CommandSourceStack> originalExecutableCommand = executable.getCommand();"),
            source.index("if (!compileExecutable(executable, functionId))"))
        self.assertLess(source.index(
            "new ContextChain<>(List.copyOf(modifiers), originalExecutable)"),
            source.index("execAccessor.functionCompiler$setCommand(wrapped);"))

    def test_exceptional_fallback_uses_original_callback_and_parsed_arguments(self):
        source=(ROOT/"src/main/java/dev/functioncompiler/ScoreAddPrototype.java").read_text()
        accessor=(ROOT/"src/main/java/dev/functioncompiler/mixin/CommandContextAccessor.java").read_text()
        for item in (
            "originalExecutableCommand,",
            "executable.getRootNode()",
            "executable.getNodes()",
            "executable.getChild()",
            "executable.getRedirectModifier()",
            "executable.isForked()",
            ".functionCompiler$getArguments()",
        ):
            self.assertIn(item,source)
        self.assertIn('@Accessor("arguments")',accessor)
        self.assertIn("Map<String, ParsedArgument<S, ?>> functionCompiler$getArguments()", accessor)
        self.assertIn('@Accessor("command")',accessor)

    def test_source_gate_and_unmodified_legacy_paths(self):
        source=(ROOT/"src/main/java/dev/functioncompiler/ScoreAddPrototype.java").read_text()
        self.assertIn("if (typedOnly && typedLiteralGuard)",source)
        self.assertIn("ContextChain<CommandSourceStack> nativeFallback = chain;",source)
        self.assertIn("if (!acceptedShape) return;",source)
        self.assertIn("!ProbeConfiguration.scoreAddPrototypeEnabled()",source)
        self.assertIn("!ProbeConfiguration.fusedRegionPrototypeEnabled()",source)
        self.assertIn("!ProbeConfiguration.bytecodeRegionPrototypeEnabled()",source)


if __name__ == "__main__":
    unittest.main()
