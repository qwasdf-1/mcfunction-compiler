#!/usr/bin/env python3
"""Pinned Minecraft 26.3 Fabric mod artifacts shared by runtime harnesses.

The canonical pin data and stack definitions live in the vendored harness
(`vendor/mc-harness`, `mc_harness.mod_stacks`) so every differential run
loads the same pinned versions. This module is the
function-compiler adapter: it resolves this project's retained jar directory
and re-exports the shared pins. Verify a jar before loading it with
`mc_harness.mod_stacks.verify_mod_jar`, or with the project's own checks where
a runner records the digest in its report.
"""

from __future__ import annotations

import sys
from pathlib import Path

# The harness package is vendored at vendor/mc-harness (frozen at 1.0.0).
MC_HARNESS_ROOT = Path(__file__).resolve().parents[1] / "vendor" / "mc-harness"
if str(MC_HARNESS_ROOT) not in sys.path:
    sys.path.insert(0, str(MC_HARNESS_ROOT))

from mc_harness import assert_version  # noqa: E402
from mc_harness.mod_stacks import (  # noqa: E402,F401
    MODS,
    STACK_MODS,
    resolve_mods_dir,
    verify_mod_jar,
)

#: The harness version these pins were verified against (roadmap step 6 pin).
HARNESS_PIN = "1.0.0"

assert_version(HARNESS_PIN)

ROOT = Path(__file__).resolve().parents[1]
MODS_DIR = resolve_mods_dir(ROOT)
