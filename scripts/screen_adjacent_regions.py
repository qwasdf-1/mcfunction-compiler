#!/usr/bin/env python3
"""Screen pinned datapacks for tick-reachable adjacent command runs.

The screen is a static, conservative approximation of the parsed-command
eligibility used by ``ScoreAddPrototype``/``FusedRegionPrototype``. It reports
three tiers:

* ``literal_score``: consecutive ``scoreboard players add/set/remove`` commands
  with a literal fake-holder/player or ``@s`` target and an integer amount.
  These are the commands exercised by the PERF-016 fixture and are definitely
  eligible when parsed.
* ``parsed_candidates``: consecutive commands drawn from the wider parsed-command
  family (score operations/resets, ``data ... storage``, and ``execute`` chains
  with score conditions/stores). A hit is a candidate for manual inspection,
  not proof of eligibility.
* ``leaf_functions``: consecutive plain ``function <id>`` calls, which
  ``LeafFunctionParser`` may turn into fusable leaf commands when the target is
  a plain-text function.

A region is only created for a run of at least two consecutive eligible
commands. Each run is annotated with whether its function is reachable from the
pack's ``minecraft:tick`` tag, only from ``minecraft:load``, or neither, so a
load-time-only run is not mistaken for an active-tick workload.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "references" / "real-world"
DEFAULT_OUTPUT_DIR = ROOT / "build" / "reports" / "datapack-screening"

FUNCTION_PATH = re.compile(r"^data/([^/]+)/functions?/(.+)\.mcfunction$")
TAG_PATH = re.compile(r"^data/([^/]+)/tags/functions?/(.+)\.json$")
COMMENT = re.compile(r"^\s*#")
CALL = re.compile(r"(?:^|\brun\s+)function\s+([#A-Za-z0-9_.:/-]+)")
SCORE_HOLDER = r"(?:#[A-Za-z0-9_.+-]+|@s|[A-Za-z0-9_.+-]+)"
OBJECTIVE = r"[A-Za-z0-9_.+-]+"
INTEGER = r"-?\d+"

LITERAL_SCORE_MUTATION = re.compile(
    rf"^scoreboard\s+players\s+(?:add|set|remove)\s+{SCORE_HOLDER}\s+{OBJECTIVE}\s+{INTEGER}$"
)
SCORE_OPERATION = re.compile(
    rf"^scoreboard\s+players\s+operation\s+{SCORE_HOLDER}\s+{OBJECTIVE}\s+\S+\s+{SCORE_HOLDER}\s+{OBJECTIVE}$"
)
SCORE_RESET = re.compile(
    rf"^scoreboard\s+players\s+reset\s+{SCORE_HOLDER}(?:\s+{OBJECTIVE})?$"
)
DATA_STORAGE = re.compile(r"^data\s+(?:modify|remove)\s+storage\s+\S+")
DATA_GET_STORAGE = re.compile(r"^data\s+get\s+storage\s+\S+")
EXECUTE_SCORE = re.compile(
    r"^execute\s+.*\b(?:scoreboard\s+players\s+(?:add|set|remove|operation|reset)"
    r"|score\s+\S+\s+\S+)"
)
LEAF_FUNCTION = re.compile(r"^function\s+[A-Za-z0-9_.:/-]+$")

TIERS = ("literal_score", "parsed_candidates", "leaf_functions")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def classify(line: str) -> str | None:
    if LITERAL_SCORE_MUTATION.match(line):
        return "literal_score"
    if (
        SCORE_OPERATION.match(line)
        or SCORE_RESET.match(line)
        or DATA_STORAGE.match(line)
        or DATA_GET_STORAGE.match(line)
        or EXECUTE_SCORE.match(line)
    ):
        return "parsed_candidate"
    if LEAF_FUNCTION.match(line):
        return "leaf_function"
    return None


@dataclass
class FunctionRecord:
    function_id: str
    name: str
    commands: list[tuple[int, str, str | None]] = field(default_factory=list)
    calls: set[str] = field(default_factory=set)


def parse_tag_entries(raw: object) -> list[str]:
    if not isinstance(raw, dict):
        return []
    values = raw.get("values")
    if not isinstance(values, list):
        return []
    entries: list[str] = []
    for value in values:
        if isinstance(value, str):
            entries.append(value)
        elif isinstance(value, dict) and isinstance(value.get("id"), str):
            entries.append(value["id"])
    return entries


def reachable_from(
    roots: list[str],
    functions: dict[str, FunctionRecord],
    tags: dict[str, list[str]],
) -> set[str]:
    reached: set[str] = set()
    pending = list(roots)
    seen_tags: set[str] = set()
    while pending:
        target = pending.pop()
        if target.startswith("#"):
            if target in seen_tags:
                continue
            seen_tags.add(target)
            pending.extend(tags.get(target, []))
            continue
        if target in reached:
            continue
        record = functions.get(target)
        if record is None:
            continue
        reached.add(target)
        pending.extend(sorted(record.calls))
    return reached


def runs_for(
    commands: list[tuple[int, str, str | None]],
    tier: str,
    min_run: int,
    reachability: str,
) -> list[dict[str, object]]:
    runs: list[dict[str, object]] = []
    current: list[tuple[int, str]] = []

    def flush() -> None:
        if len(current) >= min_run:
            runs.append(
                {
                    "start_line": current[0][0],
                    "length": len(current),
                    "sample": [text for _, text in current[:3]],
                    "reachability": reachability,
                }
            )
        current.clear()

    for line_number, text, kind in commands:
        if tier == "literal_score":
            eligible = kind == "literal_score"
        elif tier == "parsed_candidates":
            eligible = kind in {"literal_score", "parsed_candidate"}
        elif tier == "leaf_functions":
            eligible = kind == "leaf_function"
        else:
            raise ValueError(f"Unknown tier {tier!r}")
        if eligible:
            current.append((line_number, text))
        else:
            flush()
    flush()
    return runs


def screen_pack(path: Path, min_run: int, max_examples: int) -> dict[str, object]:
    payload = path.read_bytes()
    functions: dict[str, FunctionRecord] = {}
    tags: dict[str, list[str]] = {}
    with zipfile.ZipFile(path) as archive:
        for name in archive.namelist():
            function_match = FUNCTION_PATH.match(name)
            if function_match:
                namespace, function_path = function_match.groups()
                function_id = f"{namespace}:{function_path}"
                record = FunctionRecord(function_id=function_id, name=name)
                text = archive.read(name).decode("utf-8", errors="replace")
                for line_number, raw in enumerate(text.splitlines(), start=1):
                    line = raw.strip()
                    if not line or COMMENT.match(line):
                        continue
                    record.calls.update(CALL.findall(line))
                    kind = classify(line)
                    record.commands.append((line_number, line, kind))
                functions[function_id] = record
                continue
            tag_match = TAG_PATH.match(name)
            if tag_match:
                namespace, tag_path = tag_match.groups()
                tag_id = f"#{namespace}:{tag_path}"
                try:
                    raw = json.loads(archive.read(name).decode("utf-8", errors="replace"))
                except json.JSONDecodeError:
                    continue
                tags[tag_id] = parse_tag_entries(raw)

    tick_reached = reachable_from(["#minecraft:tick"], functions, tags)
    load_reached = reachable_from(["#minecraft:load"], functions, tags)

    tiers: dict[str, dict[str, object]] = {
        tier: {
            "functions_with_runs": 0,
            "total_runs": 0,
            "tick_runs": 0,
            "load_only_runs": 0,
            "off_path_runs": 0,
            "max_run": 0,
            "max_tick_run": 0,
            "examples": [],
            "top_tick_runs": [],
        }
        for tier in TIERS
    }
    for record in sorted(
        functions.values(),
        key=lambda item: (
            0
            if item.function_id in tick_reached
            else 1
            if item.function_id in load_reached
            else 2,
            item.name,
        ),
    ):
        if record.function_id in tick_reached:
            reachability = "tick"
        elif record.function_id in load_reached:
            reachability = "load"
        else:
            reachability = "off_path"
        for tier in TIERS:
            runs = runs_for(record.commands, tier, min_run, reachability)
            if not runs:
                continue
            values = tiers[tier]
            values["functions_with_runs"] += 1
            values["total_runs"] += len(runs)
            if reachability == "tick":
                values["tick_runs"] += len(runs)
                values["max_tick_run"] = max(
                    values["max_tick_run"], max(run["length"] for run in runs)
                )
            elif reachability == "load":
                values["load_only_runs"] += len(runs)
            else:
                values["off_path_runs"] += len(runs)
            values["max_run"] = max(values["max_run"], max(run["length"] for run in runs))
            for run in runs:
                if len(values["examples"]) >= max_examples:
                    break
                values["examples"].append({"function": record.name, **run})
            if reachability == "tick":
                values["top_tick_runs"].extend(
                    {"function": record.name, **run} for run in runs
                )

    for values in tiers.values():
        values["top_tick_runs"] = sorted(
            values["top_tick_runs"], key=lambda run: run["length"], reverse=True
        )[:10]

    result: dict[str, object] = {
        "pack": path.name,
        "path": str(path.relative_to(ROOT)),
        "sha256": sha256_bytes(payload),
        "bytes": len(payload),
        "functions": len(functions),
        "tags": len(tags),
        "tick_reachable_functions": len(tick_reached),
        "load_reachable_functions": len(load_reached),
    }
    result.update(tiers)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        default=DEFAULT_INPUT,
        help="directory scanned recursively for datapack .zip files",
    )
    parser.add_argument("--output", type=Path, default=None, help="JSON report path")
    parser.add_argument("--markdown", type=Path, default=None, help="Markdown summary path")
    parser.add_argument("--min-run", type=int, default=2)
    parser.add_argument("--max-examples", type=int, default=5)
    args = parser.parse_args()
    if args.min_run < 2:
        parser.error("--min-run must be at least 2 (fusion requires adjacent pairs)")
    if args.max_examples < 1:
        parser.error("--max-examples must be positive")
    return args


def markdown_summary(report: dict[str, object]) -> str:
    lines = [
        "# Adjacent-eligible datapack screen",
        "",
        f"Generated: {report['generated_at']}",
        "",
        f"Inputs: `{report['input']}` · packs: {len(report['packs'])} · "
        f"functions: {report['summary']['functions']} · minimum run: {report['min_run']}",
        "",
        "A run is tick-reachable when its function is in the transitive call/tag",
        "closure of `#minecraft:tick`. Load-only runs are kept separate because",
        "they are not active-tick workloads.",
        "",
        "| Pack | Functions | Tick-reachable | Literal tick runs | Literal runs (all) | Parsed tick runs | Leaf tick runs | Max literal tick run | Max parsed tick run |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for pack in report["packs"]:
        lines.append(
            f"| `{pack['pack']}` | {pack['functions']} | {pack['tick_reachable_functions']} | "
            f"{pack['literal_score']['tick_runs']} | {pack['literal_score']['total_runs']} | "
            f"{pack['parsed_candidates']['tick_runs']} | {pack['leaf_functions']['tick_runs']} | "
            f"{pack['literal_score']['max_tick_run']} | "
            f"{pack['parsed_candidates']['max_tick_run']} |"
        )

    def emit_runs(pack: dict[str, object], tier: str, limit: int) -> None:
        for run in pack[tier]["top_tick_runs"][:limit]:
            lines.append(
                f"- `{run['function']}:{run['start_line']}` "
                f"({run['length']} commands): `{run['sample'][0]}`"
            )

    hits = [pack for pack in report["packs"] if pack["literal_score"]["tick_runs"]]
    lines.extend(["", "## Tick-reachable literal-score runs", ""])
    if not hits:
        lines.append(
            "No pack contains a tick-reachable run of at least two literal "
            "`scoreboard players add/set/remove` commands."
        )
    for pack in hits:
        lines.append(f"### `{pack['pack']}`")
        lines.append("")
        emit_runs(pack, "literal_score", 10)
        lines.append("")

    parsed_hits = [
        pack for pack in report["packs"] if pack["parsed_candidates"]["tick_runs"]
    ]
    lines.extend(["## Largest tick-reachable parsed runs", ""])
    lines.append(
        "These include literal score mutations and the wider parsed-command "
        "family (`execute ... run scoreboard`, score operations/resets, and "
        "`data ... storage`). They are candidates for runtime confirmation, not "
        "proof that every command specializes."
    )
    lines.append("")
    if not parsed_hits:
        lines.append("No pack contains a tick-reachable parsed candidate run.")
    for pack in parsed_hits:
        lines.append(f"### `{pack['pack']}`")
        lines.append("")
        emit_runs(pack, "parsed_candidates", 8)
        lines.append("")

    load_hits = [
        pack for pack in report["packs"] if pack["literal_score"]["load_only_runs"]
    ]
    lines.extend(["## Load-only literal-score runs", ""])
    if not load_hits:
        lines.append("No pack contains a load-only literal-score run.")
    for pack in load_hits:
        lines.append(
            f"- `{pack['pack']}`: {pack['literal_score']['load_only_runs']} run(s), "
            f"max length {pack['literal_score']['max_run']}."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    packs = sorted(args.input.rglob("*.zip"))
    if not packs:
        raise SystemExit(f"No datapack .zip files under {args.input}")
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": str(args.input.relative_to(ROOT)) if args.input.is_relative_to(ROOT) else str(args.input),
        "min_run": args.min_run,
        "packs": [screen_pack(path, args.min_run, args.max_examples) for path in packs],
    }
    summary = {
        "packs": len(report["packs"]),
        "functions": sum(pack["functions"] for pack in report["packs"]),
        "packs_with_literal_tick_runs": sum(
            1 for pack in report["packs"] if pack["literal_score"]["tick_runs"]
        ),
        "literal_tick_runs": sum(pack["literal_score"]["tick_runs"] for pack in report["packs"]),
        "literal_load_only_runs": sum(
            pack["literal_score"]["load_only_runs"] for pack in report["packs"]
        ),
        "literal_off_path_runs": sum(
            pack["literal_score"]["off_path_runs"] for pack in report["packs"]
        ),
        "parsed_tick_runs": sum(pack["parsed_candidates"]["tick_runs"] for pack in report["packs"]),
        "leaf_tick_runs": sum(pack["leaf_functions"]["tick_runs"] for pack in report["packs"]),
    }
    report["summary"] = summary
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output = args.output or (DEFAULT_OUTPUT_DIR / f"adjacent-regions-{stamp}.json")
    markdown = args.markdown or output.with_suffix(".md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    markdown.write_text(markdown_summary(report), encoding="utf-8")
    print(json.dumps({"report": str(output), "markdown": str(markdown), "summary": summary}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
