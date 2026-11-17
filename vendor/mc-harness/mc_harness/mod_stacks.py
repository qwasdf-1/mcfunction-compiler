"""Pinned Minecraft 26.3 Fabric mod artifacts and stack definitions.

Extracted (roadmap step 6, batch 20) from
`function-compiler/scripts/mod_artifacts.py`, which was authored for the
Function Compiler differential harness. The mod-stack matrix is engine-agnostic
pinned data: which optimization-mod versions a differential run may load, and
which names the run's stack definitions use.

The pin digest of each jar is verified by the consuming project before a run
loads it (the jars themselves stay in the consuming project's retained
reference cache). The mods directory is resolved per project because each
project retains its own jars.
"""

from __future__ import annotations

from pathlib import Path

#: Relative location of the retained pinned-jar cache inside a consuming project.
MODS_DIR_RELATIVE = Path("references") / "real-world" / "mods-26.3"

#: Minecraft version these artifacts are pinned to.
MINECRAFT_VERSION = "26.3"

MODS = {
    "lithium": (
        "lithium-fabric-0.26.2+mc26.3.jar",
        "0be5b17ef9f6e9244cd07b24b227553a73aec0cf93158cf28099f3094c167f1b",
    ),
    "bellows": (
        "bellows-1.1.2.jar",
        "d0c7218e7e368c7d1473483881540ff78554853ff0a4f0bab098df6b3c753b67",
    ),
    "bellows113": (
        "bellows-1.1.3.jar",
        "4d9fc818d0e800c1a7414b4670c676339020749e516a50742bd18c4e3d61055c",
    ),
    "moonrise": (
        "Moonrise-Fabric-1.2.1+e53de7f.jar",
        "78911260bbf2e8053910c93de66d48709f2fd8fb2d69958e575328ffb1291fc3",
    ),
    "moonrise120": (
        "Moonrise-Fabric-1.2.0+61c1328.jar",
        "cb4890a8aeb61115b4b57aff3d4ec26c96ffdb4194d28fd7ed9d1365db3aa4d6",
    ),
    "ferritecore": (
        "ferritecore-9.0.0-fabric.jar",
        "213966c72ed967acc7392beb28a866fba301ff56b9976c2e7801c2db7de6bf22",
    ),
    "c2me": (
        "c2me-fabric-mc26.3-0.4.2-alpha.0.114.jar",
        "c93dc9638dae58e1dccd901877c3892bb969ace8eabc6459df1309654a8c6fd2",
    ),
}

STACK_MODS = {
    "fabric": (),
    "lithium": ("lithium",),
    "bellows": ("bellows",),
    "bellows-moonrise120": ("bellows", "moonrise120"),
    "bellows113": ("bellows113",),
    "bellows113-moonrise120": ("bellows113", "moonrise120"),
    "bellows113-moonrise": ("bellows113", "moonrise"),
    "lm": ("lithium", "moonrise"),
    "lb": ("lithium", "bellows"),
    "lbm": ("lithium", "bellows", "moonrise"),
    "lbm120": ("lithium", "bellows", "moonrise120"),
    "lb113": ("lithium", "bellows113"),
    "lbm113": ("lithium", "bellows113", "moonrise"),
    "lbm113120": ("lithium", "bellows113", "moonrise120"),
    "ferritecore": ("ferritecore",),
    "c2me": ("c2me",),
    "lfc": ("lithium", "ferritecore"),
    "lbmfc": ("lithium", "bellows113", "moonrise120", "ferritecore"),
    "all_opt": ("lithium", "bellows113", "moonrise120", "ferritecore", "c2me"),
}


def resolve_mods_dir(project_root: Path) -> Path:
    """The pinned-jar cache directory inside a consuming project."""
    return project_root / MODS_DIR_RELATIVE


def verify_mod_jar(path: Path, mod_key: str) -> None:
    """Verify a pinned jar's SHA-256 before a run loads it.

    A missing or mismatched jar is a hard failure: an unpinned optimization
    mod silently changes what the differential run measures.
    """
    import hashlib

    filename, expected = MODS[mod_key]
    if path.name != filename:
        raise FileNotFoundError(f"Expected pinned {mod_key} jar {filename}, found {path.name}")
    if not path.is_file():
        raise FileNotFoundError(f"Missing pinned {mod_key} jar: {path}")
    with path.open("rb") as jar:
        digest = hashlib.file_digest(jar, "sha256").hexdigest()
    if digest != expected:
        raise RuntimeError(f"Pin mismatch for {mod_key} at {path}: {digest} != {expected}")
