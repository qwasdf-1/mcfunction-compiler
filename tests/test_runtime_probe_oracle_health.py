"""Health checks for the runtime probe's differential oracles.

These checks do not start a server. They inspect the oracle table itself,
because the expensive failure modes this project has hit are properties of the
table rather than of the game:

* a fixture registered in ``DIRECT_FIXTURES`` but absent from
  ``EXPECTED_SCORES`` is never compared, because
  ``_assert_fixture_high_quota_result`` returns early on a missing entry - the
  fixture runs and can never fail;
* an all-zero, or constant, score map is an oracle that can never fail either;
* a fixture whose declared full-run value is higher than the map's top-quota
  value leaves its final cases unexecuted at every quota, so those cases are
  silently unobservable (the multiply-chain version of the predicate batch hit
  exactly this: the quota budget ran out with two cases left).

Every exemption is an explicit, named entry below with a reason. Adding a
degenerate oracle therefore requires editing this file, which is the intended
friction: a new untestable case should be a decision, not an accident.
"""

from __future__ import annotations

import ast
import re
import sys
import unittest
from collections import Counter
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from run_runtime_probe import (  # noqa: E402
    DIRECT_FIXTURES,
    EXPECTED_SCORES,
    EXTENDED_QUOTA_FIXTURES,
    QUOTAS,
    ROOT,
)

FUNCTION_DIR = ROOT / "src" / "main" / "resources" / "data" / "function_compiler_probe" / "function"
EXTENDED_QUOTAS = range(0, 17)

# Fixtures whose verification lives somewhere other than the score map. Each
# entry names where the case is asserted instead.
EXEMPT_FROM_SCORE_COMPARISON = {
    "quota_recursive": "asserted against RECURSIVE_MAX_SCORE in the nested-call "
    "debug trace pass, not through the #fcprobe score map",
}

# Fixtures whose oracle is deliberately flat, i.e. the assertion is that the
# compiled arm behaves identically while nothing accumulates.
CONSTANT_ORACLE_CONTROLS = {
    "quota_empty": "control: no command may accumulate, so a flat zero map is the claim",
}

# Fixtures that are verified by a dedicated path outside the DIRECT_FIXTURES
# sweep. Each entry names where the case is asserted instead.
EXEMPT_FROM_DIRECT_SWEEP = {
    "quota_execute_unless_exception": "asserted by a named run_case in the "
    "callback-exception pass, which invokes it and checks the raised response",
}

# A fixture header declines to close its row differentially when client packets
# are the only observable. None of the registered fixtures are in that class.
DECLARATION_PATTERN = re.compile(
    r"expected\s+((?:[01]\s*,\s*)+[01])\s*=\s*(-?\d+)",
    re.IGNORECASE,
)
CASE_LINE_PATTERN = re.compile(
    r"^execute\b.*\brun\s+scoreboard\s+players\s+add\s+#fcprobe\s+fc_probe\s+\d+\s*$"
)


class OracleRegistryTests(unittest.TestCase):
    def test_every_registered_fixture_is_compared(self) -> None:
        compared = set(EXPECTED_SCORES)
        exempt = set(EXEMPT_FROM_SCORE_COMPARISON)
        # Exemptions must name a real fixture; a stale exemption hides drift.
        self.assertEqual(
            sorted(exempt - set(DIRECT_FIXTURES)),
            [],
            "exempt names a fixture that is no longer registered",
        )
        uncovered = sorted(set(DIRECT_FIXTURES) - compared - exempt)
        self.assertEqual(uncovered, [], "fixtures with no oracle comparison")

    def test_no_oracle_exists_for_an_unregistered_fixture(self) -> None:
        orphan_exempt = set(EXEMPT_FROM_DIRECT_SWEEP)
        self.assertEqual(
            sorted(orphan_exempt - set(EXPECTED_SCORES)),
            [],
            "exemption names an oracle that does not exist",
        )
        orphans = sorted(set(EXPECTED_SCORES) - set(DIRECT_FIXTURES) - orphan_exempt)
        self.assertEqual(orphans, [], "oracle defined for an unregistered fixture")


class OracleTableSyntaxTests(unittest.TestCase):
    def test_expectation_table_has_no_duplicate_fixture_key(self) -> None:
        # A repeated key in a dict literal is not an error in Python: the last
        # value wins and the earlier one is silently discarded. While encoding
        # the batch-6 state rows, an edit added a second `state_effect_edges`
        # entry below the one it was meant to replace, so the stale map stayed
        # in effect and every arm failed against expectations nobody had
        # updated. Loaded-module inspection cannot see this, because the import
        # already collapsed the duplicate; the source has to be parsed.
        source = (SCRIPTS_DIR / "run_runtime_probe.py").read_text()
        table = None
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Assign):
                names = [t.id for t in node.targets if isinstance(t, ast.Name)]
                if "EXPECTED_SCORES" in names and isinstance(node.value, ast.Dict):
                    table = node.value
        self.assertIsNotNone(table, "EXPECTED_SCORES not found as a dict literal")
        counts = Counter(
            key.value
            for key in table.keys
            if isinstance(key, ast.Constant)
        )
        duplicated = sorted(name for name, n in counts.items() if n > 1)
        self.assertEqual(duplicated, [], "fixture appears more than once")


class OracleShapeTests(unittest.TestCase):
    def test_each_map_covers_its_registered_quota_range(self) -> None:
        for fixture, expected in EXPECTED_SCORES.items():
            if fixture in EXEMPT_FROM_DIRECT_SWEEP:
                continue
            with self.subTest(fixture=fixture):
                wanted = EXTENDED_QUOTAS if fixture in EXTENDED_QUOTA_FIXTURES else QUOTAS
                self.assertEqual(
                    sorted(expected),
                    list(wanted),
                    "quota sweep mismatch",
                )

    def test_no_map_is_degenerate(self) -> None:
        for fixture, expected in EXPECTED_SCORES.items():
            if fixture in CONSTANT_ORACLE_CONTROLS:
                continue
            if fixture in EXEMPT_FROM_DIRECT_SWEEP:
                continue
            with self.subTest(fixture=fixture):
                self.assertGreater(
                    len(set(expected.values())),
                    1,
                    "score map is constant: the oracle cannot distinguish branches",
                )
                self.assertNotEqual(
                    max(expected.values()),
                    0,
                    "score map is all-zero: the oracle cannot distinguish branches",
                )


class DeclaredFullRunTests(unittest.TestCase):
    """A declared full-run value must be reached by the quota sweep.

    The map's top-quota value is what the harness compares in every arm, so if
    it is lower than the value the fixture's own header declares, the cases the
    header is still documenting are never executed, and the oracle silently
    stops testing them.
    """

    def declarations(self) -> dict[str, int]:
        found: dict[str, int] = {}
        for path in sorted(FUNCTION_DIR.glob("*.mcfunction")):
            text = path.read_text()
            lines = [line for line in text.splitlines() if line.startswith("#")]
            comment = "\n".join(line.lstrip("#").strip() for line in lines)
            match = DECLARATION_PATTERN.search(comment)
            if match is None:
                continue
            bits = match.group(1).replace(",", "").replace(" ", "")
            declared_value = int(match.group(2))
            self.assertEqual(
                int(bits, 2),
                declared_value,
                f"{path.name}: declared bit string and value disagree",
            )
            found[path.stem] = declared_value
        return found

    def test_declared_values_are_reached_at_the_top_quota(self) -> None:
        declarations = self.declarations()
        self.assertTrue(declarations, "no fixture declares a full-run value")
        for fixture, declared in declarations.items():
            with self.subTest(fixture=fixture):
                self.assertIn(fixture, EXPECTED_SCORES, "declared fixture has no oracle")
                top_quota = max(EXPECTED_SCORES[fixture])
                self.assertEqual(
                    EXPECTED_SCORES[fixture][top_quota],
                    declared,
                    "top-quota score is below the declared full-run value: the "
                    "fixture's later cases never execute inside the quota sweep",
                )

    def test_declared_bit_count_matches_the_number_of_case_lines(self) -> None:
        declarations = self.declarations()
        for fixture, declared in declarations.items():
            path = FUNCTION_DIR / f"{fixture}.mcfunction"
            comment = "\n".join(
                line.lstrip("#").strip()
                for line in path.read_text().splitlines()
                if line.startswith("#")
            )
            match = DECLARATION_PATTERN.search(comment)
            assert match is not None
            bit_count = len(match.group(1).replace(",", "").replace(" ", ""))
            case_lines = [
                line
                for line in path.read_text().splitlines()
                if CASE_LINE_PATTERN.match(line.strip())
            ]
            with self.subTest(fixture=fixture):
                self.assertEqual(
                    len(case_lines),
                    bit_count,
                    "the header declares a different number of branch cases "
                    "than the fixture actually runs",
                )
                weights = {
                    int(line.rsplit("fc_probe", 1)[1])
                    for line in case_lines
                }
                self.assertEqual(
                    len(weights),
                    bit_count,
                    "two cases share a weight: the folded oracle is not injective",
                )
                # A fixture whose final case takes no branch cannot distinguish
                # "the tail executed and was false" from "the tail never
                # executed", so the declared value is only a completion signal
                # if the last bit is set.
                self.assertTrue(
                    match.group(1).replace(",", "").replace(" ", "").endswith("1"),
                    "the final case takes no branch, so a truncated tail is "
                    "indistinguishable from an executed one in the score map",
                )
                for weight in weights:
                    self.assertLessEqual(
                        weight,
                        1 << (bit_count - 1),
                        "a weight is not a distinct power of two for this "
                        "number of cases",
                    )


if __name__ == "__main__":
    unittest.main()
