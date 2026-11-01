from __future__ import annotations

import unittest
from pathlib import Path

from scripts.doc_hygiene.doc_links import (
    documentation_path_check,
    extract_path_refs,
    is_external_link,
    is_forbidden_absolute_path,
    is_placeholder,
    split_ref_fragment,
)
from scripts.doc_hygiene.generate_repo_truth import (
    DOCS,
    REPO,
    ROOT_DOCS,
    symbol_for_line,
)
from scripts.doc_hygiene.repo_inventory import (
    is_excluded_repo_path,
    matches_excluded_path_prefix,
)


class DocHygieneInventoryTests(unittest.TestCase):
    def test_excludes_build_and_gradle_paths(self) -> None:
        build_path = REPO / "build" / "classes" / "Test.class"
        gradle_path = REPO / ".gradle" / "caches" / "test.bin"
        run_path = REPO / "run" / "server.log"

        self.assertTrue(is_excluded_repo_path(build_path, REPO))
        self.assertTrue(is_excluded_repo_path(gradle_path, REPO))
        self.assertTrue(is_excluded_repo_path(run_path, REPO))
        self.assertTrue(matches_excluded_path_prefix(build_path, REPO))

    def test_retains_source_and_docs(self) -> None:
        src_path = REPO / "src" / "main" / "java" / "dev" / "functioncompiler" / "ScoreAddPrototype.java"
        doc_path = REPO / "docs" / "reference" / "features" / "scoreboard-specialization.md"

        self.assertFalse(is_excluded_repo_path(src_path, REPO))
        self.assertFalse(is_excluded_repo_path(doc_path, REPO))


class DocHygieneLinkTests(unittest.TestCase):
    def test_identifies_external_and_placeholder_links(self) -> None:
        self.assertTrue(is_external_link("https://github.com/example/repo"))
        self.assertFalse(is_external_link("file:///absolute/path"))
        self.assertTrue(is_forbidden_absolute_path("file:///absolute/path"))
        self.assertTrue(is_forbidden_absolute_path("/home/operator-qwasdf/projects/mc-mods"))
        self.assertFalse(is_forbidden_absolute_path("docs/reference/features/inventory.md"))
        self.assertFalse(is_external_link("docs/reference/features/inventory.md"))

        self.assertTrue(is_placeholder("tests/fixtures/<feature>/"))
        self.assertTrue(is_placeholder("build/*.jar"))
        self.assertFalse(is_placeholder("docs/verification.md"))

    def test_splits_fragments(self) -> None:
        base, frag = split_ref_fragment("docs/verification.md#testing-evidence")
        self.assertEqual(base, "docs/verification.md")
        self.assertEqual(frag, "testing-evidence")

        base_line, line_num = split_ref_fragment("scripts/run_score_add_ab.py:882")
        self.assertEqual(base_line, "scripts/run_score_add_ab.py")
        self.assertEqual(line_num, "882")

        base_no_frag, frag_none = split_ref_fragment("README.md")
        self.assertEqual(base_no_frag, "README.md")
        self.assertIsNone(frag_none)

    def test_all_active_documentation_references_resolve(self) -> None:
        checked, unresolved = documentation_path_check(
            REPO, DOCS, ROOT_DOCS, {"archive", "generated"}
        )
        self.assertGreater(checked, 100)
        self.assertEqual(unresolved, [])


class DocHygieneSymbolExtractionTests(unittest.TestCase):
    def test_extracts_java_symbols(self) -> None:
        java_cls = "public final class ScoreAddPrototype {"
        java_mixin = "@Mixin(ServerFunctionLibrary.class)"
        java_method = "    public static void executeStep() {"

        self.assertEqual(symbol_for_line("java", java_cls), "class ScoreAddPrototype")
        self.assertEqual(symbol_for_line("java", java_mixin), "@Mixin(ServerFunctionLibrary)")
        self.assertEqual(symbol_for_line("java", java_method), "method executeStep()")

    def test_extracts_python_symbols(self) -> None:
        py_cls = "class TestRunner:"
        py_def = "def run_benchmark():"

        self.assertEqual(symbol_for_line("py", py_cls), "class TestRunner")
        self.assertEqual(symbol_for_line("py", py_def), "def run_benchmark()")


if __name__ == "__main__":
    unittest.main()
