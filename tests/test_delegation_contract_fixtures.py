"""Static checks on the delegation-contract fixtures and the status keys.

These checks exist because the runtime measurement can be disarmed silently.
`ProbeStatus` reports per-function specialization counters for the
delegation-contract fixtures; a fixture that was renamed, deleted, or quietly
changed into a specializable shape would read zero, and a zero reading is what
the contract asserts - so the check would pass while proving nothing. The
runtime run cannot see that, because a missing function is indistinguishable
from an unspecialized one in the counter.

Checking the wiring statically keeps the runtime assertion honest:

* every fixture the status command reports on actually exists;
* the positive control really contains a specializable shape, so its counter
  can move;
* the declined fixture really contains no specializable shape, so zero means
  "declined" and not "the fixture is gone";
* the client-packet fixture really contains only client-packet commands.

These are properties of the fixture files, not of a running server, so they are
checked here rather than in the runtime probe.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
STATUS_SOURCE = (
    REPO / "src" / "main" / "java" / "dev" / "functioncompiler" / "ProbeStatus.java"
)
FUNCTION_DIR = (
    REPO / "src" / "main" / "resources" / "data" / "function_compiler_probe" / "function"
)

# Fixtures whose counters the status command exposes for the contract, with the
# status key prefix each one is reported under.
DELEGATION_KEYS = {
    "control": "delegation_control",
    "selector": "delegation_selector",
    "client_packet": "delegation_client_packet",
}

# A `scoreboard players` line carrying a `#` fake holder is a shape the
# specialized scoreboard path can accept; a selector or `@s` operand alone is
# declined. The declined fixture therefore must contain no `#` at all, so its
# refusal to specialize does not depend on which operand the compiler checks
# first.
SPECIALIZABLE_TARGET = re.compile(
    r"^scoreboard\s+players\s+\S+\s+(#\S+)\s+\S+"
)
CLIENT_PACKET_COMMANDS = {
    "title",
    "playsound",
    "stopsound",
    "particle",
}


def delegation_fixture_names(source: str) -> dict[str, str]:
    """Read the DELEGATION_* Identifier constants out of ProbeStatus.java."""

    names: dict[str, str] = {}
    for match in re.finditer(
        r"private static final Identifier (\w+)\s*=\s*Identifier\.fromNamespaceAndPath\(\s*"
        r'"function_compiler_probe",\s*"([a-z0-9_]+)"',
        source,
    ):
        constant, function_name = match.group(1), match.group(2)
        key = constant[len("DELEGATION_"):].lower() if constant.startswith("DELEGATION_") else None
        if key is not None:
            names[key] = function_name
    return names


def body(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text().splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


class DelegationFixtureWiringTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(STATUS_SOURCE.is_file(), f"missing {STATUS_SOURCE}")
        self.names = delegation_fixture_names(STATUS_SOURCE.read_text())

    def test_status_declares_every_delegation_fixture(self) -> None:
        self.assertEqual(
            sorted(self.names),
            sorted(DELEGATION_KEYS),
            "ProbeStatus must declare exactly the delegation fixtures the "
            "runtime probe reports on",
        )

    def test_every_declared_fixture_exists(self) -> None:
        for key, name in self.names.items():
            path = FUNCTION_DIR / f"{name}.mcfunction"
            with self.subTest(fixture=key):
                self.assertTrue(
                    path.is_file(),
                    f"{name}.mcfunction is missing: its per-function counter "
                    f"would read zero, which is the signal the contract relies on",
                )

    def test_status_reports_every_declared_fixture(self) -> None:
        source = STATUS_SOURCE.read_text()
        for key in self.names:
            with self.subTest(fixture=key):
                self.assertIn(
                    f"delegation_{key}_compiled=",
                    source,
                    f"delegation_{key} is declared but not reported, so a "
                    f"specialized command in it would be invisible",
                )


class DelegationFixtureShapeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(STATUS_SOURCE.is_file())
        self.names = delegation_fixture_names(STATUS_SOURCE.read_text())

    def control_path(self) -> Path:
        return FUNCTION_DIR / f"{self.names['control']}.mcfunction"

    def selector_path(self) -> Path:
        return FUNCTION_DIR / f"{self.names['selector']}.mcfunction"

    def client_packet_path(self) -> Path:
        return FUNCTION_DIR / f"{self.names['client_packet']}.mcfunction"

    def test_control_has_a_specializable_command(self) -> None:
        lines = body(self.control_path())
        specializable = [
            line for line in lines if SPECIALIZABLE_TARGET.match(line)
        ]
        self.assertTrue(
            specializable,
            "the positive control must contain at least one fake-holder "
            "scoreboard command, or its counter can never move and the zero "
            "readings it guards are unverifiable",
        )

    def test_declined_fixture_has_no_specializable_command(self) -> None:
        lines = body(self.selector_path())
        specializable = [
            line
            for line in lines
            if line.startswith("scoreboard players ") and "#" in line
        ]
        self.assertEqual(
            specializable,
            [],
            "a fake-holder operand in the declined fixture makes its refusal "
            "to specialize ambiguous, and the fixture must prove the refusal "
            "without depending on which other operand the compiler checks first",
        )
        self.assertTrue(
            lines,
            "the declined fixture is empty, so it proves nothing",
        )

    def test_client_packet_fixture_has_only_client_packet_commands(self) -> None:
        lines = body(self.client_packet_path())
        self.assertTrue(lines, "the client-packet fixture is empty")
        for line in lines:
            command = line.split()[0]
            with self.subTest(command=line):
                self.assertIn(
                    command,
                    CLIENT_PACKET_COMMANDS,
                    "a command outside the client-packet set belongs in a "
                    "different fixture, because it may have a server-side "
                    "effect that this contract does not cover",
                )


if __name__ == "__main__":
    unittest.main()
