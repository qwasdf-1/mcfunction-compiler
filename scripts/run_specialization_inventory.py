#!/usr/bin/env python3
"""Inventory the addressable specialization work in the pinned real datapacks.

This is the first step of the compiler-widening proposal
(``docs/v1/plans/compiler-coverage-widening-proposal-v0.1.md``, H2-first): a
metrics-only census that ranks the pinned packs by the work each optimization
could actually reach, instead of counting raw command occurrences.

The census is deliberately static and hermetic: it reads the pinned pack zips
(verifying their recorded SHA-256), walks the functions reachable from
``minecraft:tick`` and ``minecraft:load``, and classifies every command against
the compiler's real eligibility rule:

* ``FusedRegionPrototype`` fuses adjacent commands only when the parsed command
  is a ``FusableCommand`` **and** ``context.isForked()`` is false, so a command
  behind ``execute as``/``at``/``on``/``summon`` is *not* addressable by the
  current engine. The census separates lexically forked lines from top-level
  and context-modifier (``positioned``/``facing``/``rotated``/``anchored``/
  ``align``/``in``) lines, which stay non-forked.
* A ``function`` call is an inlining candidate only when its target is a pure
  leaf in the sense of ``LeafFunctionParser.isPureLeaf`` (1..64 entries, no
  ``function``/``return`` roots).
* Macro functions are the H4 pool: functions containing ``$(...)``
  placeholders and call sites of the form ``function <id> with ...``.

The output answers the question the static 2026-11-03 screen could not: how
much of each pack's *reachable hot path* sits behind the fork barrier, how much
is adjacent and eligible today, and how much per-entity macro expansion exists.
It does not execute the packs; runtime confirmation of the ranked candidates is
a separate campaign.

Usage:
    python3 scripts/run_specialization_inventory.py
    python3 scripts/run_specialization_inventory.py --packs veinminer
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "build" / "benchmarks" / "COVERAGE-INVENTORY"

#: The pinned real-datapack family. Every entry carries the recorded SHA-256
#: so a pack swap fails the census instead of silently changing the ranking.
PACKS: dict[str, dict[str, object]] = {
    "veinminer": {
        "path": ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip",
        "sha256": "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e",
        "label": "Vein Miner 5.3.0",
    },
    "dynamic-lights": {
        "path": (
            ROOT
            / "references/real-world/dynamic-lights-creepermeyt"
            / "DynamicLightsByCreepermeYT_v1.4.6.zip"
        ),
        "sha256": "afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20",
        "label": "Dynamic Lights 1.4.6",
    },
    "everything-clings": {
        "path": ROOT / "references/real-world/candidates/everything-clings-1.0.0.zip",
        "sha256": "dcb9f5398f4840375f5ade0fe47f596071644a7a447dd0d9a6e99737d71e5c75",
        "label": "Everything Clings 1.0.0",
    },
    "spawn-animations": {
        "path": (
            ROOT
            / "references/real-world/spawn-animations"
            / "spawnanimations-v1.11.6-mc1.17-26.3.9-datapack.zip"
        ),
        "sha256": "7f467a0870d2445511f652b1d246b2adac54a4051ff49a1746a2992fab86dbe6",
        "label": "Spawn Animations 1.11.6",
    },
}

#: ``execute`` subcommands that create a forked context in vanilla's execution
#: chain (the condition ``FusedRegionPrototype.fusedCommand`` tests).
FORK_SUBCOMMANDS = {"as", "at", "on", "summon"}

#: ``execute`` subcommands that modify the source but keep one context.
CONTEXT_SUBCOMMANDS = {"align", "anchored", "facing", "in", "positioned", "rotated"}

#: The leaf command families the compiler wraps as ``FusableCommand``. The
#: mapping is by command syntax because the census reads pack text, not parsed
#: Brigadier nodes; the class names are the implementing wrappers.
LEAF_FAMILIES: tuple[tuple[tuple[str, ...], str], ...] = (
    (("scoreboard", "players", "add"), "score-add"),
    (("scoreboard", "players", "remove"), "score-add"),
    (("scoreboard", "players", "set"), "score-store"),
    (("scoreboard", "players", "reset"), "score-reset"),
    (("scoreboard", "players", "operation"), "score-operation"),
    (("data", "get"), "data-get"),
    (("data", "modify"), "data-store"),
    (("data", "merge"), "data-storage"),
)

#: ``scoreboard players add #holder objective n`` - the literal fake-holder
#: family ScoreAddPrototype covers today.
FAKE_HOLDER_ADD = re.compile(
    r"^scoreboard\s+players\s+add\s+#[A-Za-z0-9_.+-]+\s+\S+\s+-?\d+$"
)

#: A macro call site: ``function <id> with <args>``.
MACRO_WITH_CALL = re.compile(
    r"\bfunction\s+(#?[a-z0-9_.-]+:[a-z0-9_./-]+)\s+with\b"
)

#: A function call: ``function <id>`` or ``function #<tag>``.
FUNCTION_CALL = re.compile(
    r"\bfunction\s+(#?[a-z0-9_.-]+:[a-z0-9_./-]+)"
)

#: A self-rescheduling call: ``schedule function <id> <time>``. Packs such as
#: Dynamic Lights drive their tick loop this way instead of a tick tag.
SCHEDULE_CALL = re.compile(
    r"\bschedule\s+function\s+(#?[a-z0-9_.-]+:[a-z0-9_./-]+)"
)

#: A macro placeholder inside a function body.
MACRO_PLACEHOLDER = re.compile(r"\$\(")


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def split_tokens(text: str) -> list[str]:
    """Split a command line on top-level whitespace.

    Bracketed selector/NBT payloads, quoted strings, and their escapes are kept
    intact so an ``as`` inside ``@e[tag=as]`` is not mistaken for the execute
    subcommand.
    """
    tokens: list[str] = []
    buffer: list[str] = []
    depth = 0
    quote = False
    escaped = False
    for character in text:
        if escaped:
            buffer.append(character)
            escaped = False
            continue
        if character == "\\" and quote:
            buffer.append(character)
            escaped = True
            continue
        if character == '"':
            quote = not quote
            buffer.append(character)
            continue
        if not quote:
            if character in "[{":
                depth += 1
            elif character in "]}":
                depth = max(0, depth - 1)
            elif character.isspace() and depth == 0:
                if buffer:
                    tokens.append("".join(buffer))
                    buffer.clear()
                continue
        buffer.append(character)
    if buffer:
        tokens.append("".join(buffer))
    return tokens


def leaf_family(command: str) -> str | None:
    """Return the compiler's leaf-family name for a bare command, if any."""
    tokens = split_tokens(command)
    for prefix, family in LEAF_FAMILIES:
        if tuple(tokens[: len(prefix)]) == prefix:
            return family
    if tokens[:2] == ["return", "run"]:
        return "tail-call"
    return None


def parse_execute(line: str) -> tuple[bool, bool, str | None]:
    """Split an ``execute`` line into (is_execute, forked, inner command).

    ``forked`` is true when the chain contains a fork-creating subcommand before
    ``run``. ``inner`` is the command after ``run``, or None when the line is
    not an execute command or has no run clause (``execute if ...`` alone is a
    condition-only command, not a fusable leaf).
    """
    tokens = split_tokens(line)
    if not tokens or tokens[0] != "execute":
        return False, False, None
    forked = False
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "run":
            inner = " ".join(tokens[index + 1 :])
            return True, forked, inner or None
        if token in FORK_SUBCOMMANDS:
            forked = True
        index += 1
    return True, forked, None


def is_pure_leaf(entries: list[str]) -> bool:
    """Match ``LeafFunctionParser.isPureLeaf`` on a function's command lines."""
    if not entries or len(entries) > 64:
        return False
    for entry in entries:
        if MACRO_PLACEHOLDER.search(entry):
            # Macro functions are not PlainTextFunction instances, so the
            # inliner never treats them as leaves.
            return False
        tokens = split_tokens(entry)
        if not tokens:
            continue
        if tokens[0] in {"function", "return"}:
            return False
    return True


class Pack:
    """One pinned pack's function bodies and tags, read from its zip."""

    def __init__(self, name: str, path: Path, sha256: str) -> None:
        self.name = name
        self.path = path
        self.sha256 = sha256
        self.functions: dict[str, list[str]] = {}
        self.tags: dict[str, list[str]] = {}
        self._read()

    def _read(self) -> None:
        with zipfile.ZipFile(self.path) as archive:
            names = archive.namelist()
            # A pack may carry legacy `functions/` copies for older Minecraft
            # versions next to the 1.21+ `function/` path. A 26.3 server loads
            # only `function/`, so prefer it per namespace and fall back to
            # `functions/` only when that namespace has no modern entries.
            modern_namespaces = {
                parts[1]
                for entry in names
                if (parts := entry.split("/")) and len(parts) >= 4
                and parts[0] == "data"
                and parts[2] == "function"
                and entry.endswith(".mcfunction")
            }
            modern_tag_namespaces = {
                parts[1]
                for entry in names
                if (parts := entry.split("/")) and len(parts) >= 5
                and parts[0] == "data"
                and parts[2] == "tags"
                and parts[3] == "function"
                and entry.endswith(".json")
            }
            for entry in names:
                parts = entry.split("/")
                if len(parts) < 4 or parts[0] != "data":
                    continue
                namespace = parts[1]
                if parts[2] in {"function", "functions"} and entry.endswith(".mcfunction"):
                    marker = "function" if namespace in modern_namespaces else "functions"
                    if parts[2] != marker:
                        continue
                    relative = "/".join(parts[3:])[: -len(".mcfunction")]
                    function_id = f"{namespace}:{relative}"
                    text = archive.read(entry).decode("utf-8", errors="replace")
                    self.functions[function_id] = command_lines(text)
                elif (
                    parts[2] == "tags"
                    and len(parts) >= 5
                    and parts[3] in {"function", "functions"}
                    and entry.endswith(".json")
                ):
                    marker = (
                        "function"
                        if namespace in modern_tag_namespaces
                        else "functions"
                    )
                    if parts[3] != marker:
                        continue
                    relative = "/".join(parts[4:])[: -len(".json")]
                    tag_id = f"{namespace}:{relative}"
                    try:
                        payload = json.loads(
                            archive.read(entry).decode("utf-8", errors="replace")
                        )
                    except json.JSONDecodeError:
                        continue
                    values = payload.get("values", [])
                    self.tags[tag_id] = [
                        value["id"] if isinstance(value, dict) else value
                        for value in values
                    ]

    def resolve(self, reference: str) -> list[str]:
        """Expand a function or tag reference to function ids."""
        if reference.startswith("#"):
            resolved: list[str] = []
            for value in self.tags.get(reference[1:], []):
                resolved.extend(self.resolve(value))
            return resolved
        return [reference] if reference in self.functions else []

    def reachable(self, roots: tuple[str, ...]) -> set[str]:
        """Functions reachable from the given entry tags through calls."""
        seen: set[str] = set()
        pending: list[str] = []
        for root in roots:
            pending.extend(self.resolve(f"#{root}"))
        while pending:
            function_id = pending.pop()
            if function_id in seen or function_id not in self.functions:
                continue
            seen.add(function_id)
            for line in self.functions[function_id]:
                for match in FUNCTION_CALL.finditer(line):
                    pending.extend(self.resolve(match.group(1)))
        return seen

    def scheduled_from(self, roots: tuple[str, ...]) -> set[str]:
        """Functions driven by a self-rescheduling loop rooted at the tags.

        Dynamic Lights and similar packs schedule their tick loop from
        ``minecraft:load`` instead of a tick tag; those functions are tick-path
        work even though a tick tag never names them.
        """
        scheduled: set[str] = set()
        for function_id in self.reachable(roots):
            for line in self.functions[function_id]:
                for match in SCHEDULE_CALL.finditer(line):
                    scheduled.update(self.resolve(match.group(1)))
        seen: set[str] = set()
        pending = list(scheduled)
        while pending:
            function_id = pending.pop()
            if function_id in seen or function_id not in self.functions:
                continue
            seen.add(function_id)
            for line in self.functions[function_id]:
                for match in FUNCTION_CALL.finditer(line):
                    pending.extend(self.resolve(match.group(1)))
        return seen


def normalize_command_line(line: str) -> str:
    """Strip a macro line's leading ``$`` marker.

    A macro function body line starts with ``$`` to mark that it is
    parameterized; the marker is not part of the command. Classification and
    reachability must see the underlying command, or every macro body command
    disappears from the census.
    """
    stripped = line.strip()
    if stripped.startswith("$"):
        return stripped[1:].lstrip()
    return stripped


def command_lines(text: str) -> list[str]:
    """Return the non-comment, non-blank command lines of a function file."""
    lines: list[str] = []
    for raw in text.splitlines():
        stripped = normalize_command_line(raw)
        if not stripped or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return lines


def function_profile(pack: Pack, function_id: str) -> dict[str, object]:
    """Classify one function's lines against the compiler's eligibility rules."""
    lines = pack.functions[function_id]
    leaf_lines = 0
    context_lines = 0
    forked_lines = 0
    execute_lines = 0
    inline_calls = 0
    macro_calls = 0
    fake_holder_adds = 0
    eligible_flags: list[bool] = []

    for line in lines:
        is_execute, forked, inner = parse_execute(line)
        command_text = inner if is_execute and inner is not None else line
        family = leaf_family(command_text)

        inlined_call = False
        if family is None and command_text.startswith("function "):
            for match in FUNCTION_CALL.finditer(command_text):
                reference = match.group(1)
                if reference.startswith("#"):
                    continue
                target = pack.functions.get(reference)
                if target is not None and is_pure_leaf(target):
                    inlined_call = True
                    inline_calls += 1
                    break

        for _match in MACRO_WITH_CALL.finditer(line):
            macro_calls += 1

        if is_execute:
            execute_lines += 1
            if forked:
                forked_lines += 1
                eligible_flags.append(False)
                continue
            if inner is not None and (family is not None or inlined_call):
                context_lines += 1
                eligible_flags.append(True)
            else:
                eligible_flags.append(False)
            continue

        if family is not None or inlined_call:
            if family is not None:
                leaf_lines += 1
            eligible_flags.append(True)
        else:
            eligible_flags.append(False)

        if family == "score-add" and FAKE_HOLDER_ADD.match(command_text):
            fake_holder_adds += 1

    runs = adjacent_runs(eligible_flags)
    return {
        "function": function_id,
        "command_lines": len(lines),
        "leaf_lines": leaf_lines,
        "context_lines": context_lines,
        "forked_lines": forked_lines,
        "execute_lines": execute_lines,
        "inline_calls": inline_calls,
        "macro_calls": macro_calls,
        "fake_holder_adds": fake_holder_adds,
        "adjacent_runs": runs["count"],
        "adjacent_run_commands": runs["commands"],
        "longest_run": runs["longest"],
        "macro_function": any(
            MACRO_PLACEHOLDER.search(line) for line in lines
        ),
    }


def adjacent_runs(flags: list[bool]) -> dict[str, int]:
    """Count maximal runs of adjacent eligible commands."""
    count = 0
    commands = 0
    longest = 0
    current = 0
    for flag in flags + [False]:
        if flag:
            current += 1
            continue
        if current >= 2:
            count += 1
            commands += current
            longest = max(longest, current)
        current = 0
    return {"count": count, "commands": commands, "longest": longest}


def summarize_pack(pack: Pack) -> dict[str, object]:
    """Aggregate the census for one pack, overall and for its tick entry."""
    reachable = pack.reachable(("minecraft:tick", "minecraft:load"))
    tick_functions = pack.reachable(("minecraft:tick",)) | pack.scheduled_from(
        ("minecraft:load",)
    )
    scheduled_functions = pack.scheduled_from(("minecraft:load",)) - pack.reachable(
        ("minecraft:tick",)
    )

    profiles = {function_id: function_profile(pack, function_id) for function_id in reachable}
    totals = {
        "functions_total": len(pack.functions),
        "functions_reachable": len(reachable),
        "functions_tick": len(tick_functions),
        "functions_scheduled": len(scheduled_functions),
        "command_lines_reachable": sum(p["command_lines"] for p in profiles.values()),
        "command_lines_tick": sum(
            profiles[function_id]["command_lines"] for function_id in tick_functions
        ),
        "leaf_lines": sum(p["leaf_lines"] for p in profiles.values()),
        "context_lines": sum(p["context_lines"] for p in profiles.values()),
        "forked_lines": sum(p["forked_lines"] for p in profiles.values()),
        "execute_lines": sum(p["execute_lines"] for p in profiles.values()),
        "inline_calls": sum(p["inline_calls"] for p in profiles.values()),
        "macro_calls": sum(p["macro_calls"] for p in profiles.values()),
        "fake_holder_adds": sum(p["fake_holder_adds"] for p in profiles.values()),
        "adjacent_runs": sum(p["adjacent_runs"] for p in profiles.values()),
        "adjacent_run_commands": sum(
            p["adjacent_run_commands"] for p in profiles.values()
        ),
        "longest_run": max(
            (p["longest_run"] for p in profiles.values()), default=0
        ),
        "macro_functions": sum(1 for p in profiles.values() if p["macro_function"]),
    }
    tick_profiles = {fid: profiles[fid] for fid in tick_functions}
    totals.update(
        {
            "tick_leaf_lines": sum(p["leaf_lines"] for p in tick_profiles.values()),
            "tick_context_lines": sum(p["context_lines"] for p in tick_profiles.values()),
            "tick_forked_lines": sum(p["forked_lines"] for p in tick_profiles.values()),
            "tick_adjacent_runs": sum(p["adjacent_runs"] for p in tick_profiles.values()),
            "tick_adjacent_run_commands": sum(
                p["adjacent_run_commands"] for p in tick_profiles.values()
            ),
            "tick_macro_calls": sum(p["macro_calls"] for p in tick_profiles.values()),
            "tick_fake_holder_adds": sum(
                p["fake_holder_adds"] for p in tick_profiles.values()
            ),
        }
    )
    totals["forked_share"] = (
        round(totals["forked_lines"] / totals["execute_lines"], 4)
        if totals["execute_lines"]
        else 0.0
    )
    return {"pack": pack.name, "totals": totals, "functions": profiles}


def render_markdown(results: list[dict[str, object]]) -> str:
    """Render the census as a human-readable ranking."""
    ranked = sorted(
        results,
        key=lambda result: (
            result["totals"]["tick_adjacent_run_commands"],
            result["totals"]["adjacent_run_commands"],
            result["totals"]["tick_macro_calls"],
        ),
        reverse=True,
    )
    lines = [
        "# Specialization inventory (H2-first, static census)",
        "",
        "Reachable from `minecraft:tick` + `minecraft:load`, classified against",
        "the compiler's real eligibility rules: forked `execute` contexts are not",
        "addressable by fused regions; `function` calls count as inlining",
        "candidates only when the target is a pure leaf.",
        "",
        "| Pack | Reachable fns | Command lines | Tick lines | Forked `execute` | Forked share | Leaf lines | Context-modifier lines | Adjacent runs (tick) | Adjacent cmds (tick) | Longest run | Fake-holder adds | Macro fns | Macro `with` (tick) |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for result in ranked:
        totals = result["totals"]
        lines.append(
            "| {pack} | {functions_reachable} | {command_lines_reachable} | "
            "{command_lines_tick} | {forked_lines} | {forked_share:.1%} | "
            "{leaf_lines} | {context_lines} | {tick_adjacent_runs} | "
            "{tick_adjacent_run_commands} | {longest_run} | {fake_holder_adds} | "
            "{macro_functions} | {tick_macro_calls} |".format(
                pack=result["pack"], **totals
            )
        )
    lines.extend(
        [
            "",
            "`Adjacent runs (tick)` counts maximal runs of >=2 adjacent eligible",
            "commands inside tick-reachable functions - the unit fused regions",
            "actually compile. `Context-modifier lines` are non-forked `execute`",
            "lines whose inner command is a leaf family (`positioned`, `facing`,",
            "`rotated`, `anchored`, `align`, `in`); `forked lines` are `execute`",
            "chains containing `as`, `at`, `on`, or `summon`, which",
            "`FusedRegionPrototype.fusedCommand` rejects. `Macro with (tick)` counts",
            "`function <id> with ...` call sites in tick-reachable functions - the",
            "H4 addressable pool.",
            "",
            "Static limitation: lexical fork status is per line. A function called",
            "from a forked context inherits that context at runtime even when its",
            "own lines are top-level; the per-function JSON records the lexical",
            "counts so a runtime pass can refine them.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--packs",
        nargs="*",
        choices=tuple(PACKS),
        default=list(PACKS),
        help="Packs to census (default: all pinned packs).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output directory (default: build/benchmarks/COVERAGE-INVENTORY/<timestamp>).",
    )
    args = parser.parse_args()

    from datetime import datetime, timezone

    output = args.output or OUTPUT_ROOT / datetime.now(timezone.utc).strftime(
        "%Y%m%dT%H%M%SZ"
    )
    output.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, object]] = []
    for name in args.packs:
        spec = PACKS[name]
        path = spec["path"]
        expected = spec["sha256"]
        if not path.is_file():
            raise FileNotFoundError(f"Missing pinned pack {name}: {path}")
        actual = sha256_file(path)
        if actual != expected:
            raise RuntimeError(
                f"Pinned pack fingerprint mismatch for {name}: {actual} != {expected}"
            )
        pack = Pack(name, path, actual)
        result = summarize_pack(pack)
        result["label"] = spec["label"]
        result["path"] = str(path.relative_to(ROOT))
        result["sha256"] = actual
        results.append(result)
        print(
            f"{name}: {result['totals']['functions_reachable']} reachable functions, "
            f"{result['totals']['command_lines_tick']} tick lines, "
            f"{result['totals']['tick_adjacent_run_commands']} adjacent tick commands, "
            f"{result['totals']['tick_macro_calls']} macro calls"
        )

    (output / "inventory.json").write_text(
        json.dumps({"packs": results}, indent=2) + "\n", encoding="utf-8"
    )
    markdown = render_markdown(results)
    (output / "inventory.md").write_text(markdown, encoding="utf-8")
    print(f"Wrote {output / 'inventory.json'}")
    print(f"Wrote {output / 'inventory.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
