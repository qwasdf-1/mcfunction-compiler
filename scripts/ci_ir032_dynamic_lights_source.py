#!/usr/bin/env python3
"""IR-032 Gate A: fetch and statically census the exact pinned Dynamic Lights pack."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PACK = ROOT / "references/real-world/dynamic-lights-creepermeyt/DynamicLightsByCreepermeYT_v1.4.6.zip"
OUT = ROOT / "build/reports/COMPILER-IR-032-DYNAMIC-LIGHTS-SOURCE"
VERSION_ID = "9JACtwPz"
FILENAME = "DynamicLightsByCreepermeYT_v1.4.6.zip"
PACK_SHA256 = "afc086a16e49a1f292a9bf694f231923579aede8da426f9608f5ece7bfbb9c20"
MAX_DOWNLOAD = 80_000_000

FUNCTION_PATH = re.compile(
    r"^data/([a-z0-9_.-]+)/(?:function|functions)/(.+)\.mcfunction$"
)
TAG_PATH = re.compile(
    r"^data/([a-z0-9_.-]+)/tags/(?:function|functions)/(.+)\.json$"
)
FUNCTION_CALL = re.compile(
    r"(?<![A-Za-z0-9_])function\s+(#[a-z0-9_.-]+:[a-z0-9_./-]+|[a-z0-9_.-]+:[a-z0-9_./-]+)"
)
SCHEDULE_CALL = re.compile(
    r"(?<![A-Za-z0-9_])schedule\s+function\s+([a-z0-9_.-]+:[a-z0-9_./-]+)\s+\S+"
)


def fetch_bytes(url: str, maximum: int = MAX_DOWNLOAD) -> bytes:
    request = urllib.request.Request(
        url, headers={"User-Agent": "MCFC-IR032-pinned-source-audit/1.0"})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read(maximum + 1)
    if len(data) > maximum:
        raise ValueError(f"Publisher response exceeds {maximum} byte cap")
    return data


def fetch_pinned_pack() -> dict:
    metadata = json.loads(fetch_bytes(
        f"https://api.modrinth.com/v2/version/{VERSION_ID}", 2_000_000))
    if metadata.get("id") != VERSION_ID:
        raise AssertionError("Modrinth version ID drift")
    if "1.4.6" not in metadata.get("version_number", ""):
        raise AssertionError(f"Unexpected Dynamic Lights version: {metadata.get('version_number')}")
    files = [item for item in metadata.get("files", [])
             if item.get("filename") == FILENAME]
    if len(files) != 1:
        raise AssertionError(f"Expected one exact publisher file {FILENAME}, found {len(files)}")
    data = fetch_bytes(files[0]["url"])
    digest = hashlib.sha256(data).hexdigest()
    if digest != PACK_SHA256:
        raise AssertionError(f"Dynamic Lights SHA mismatch: {digest} expected {PACK_SHA256}")
    PACK.parent.mkdir(parents=True, exist_ok=True)
    PACK.write_bytes(data)
    return {
        "version_id": VERSION_ID,
        "version_number": metadata["version_number"],
        "filename": FILENAME,
        "sha256": digest,
        "bytes": len(data),
        "url": files[0]["url"],
    }


def supports_format(formats, target: int = 121) -> bool:
    if isinstance(formats, int):
        return formats == target
    if isinstance(formats, dict):
        low = formats.get("min_inclusive", formats.get("min_format", 0))
        high = formats.get("max_inclusive", formats.get("max_format", 2**31 - 1))
        return int(low) <= target <= int(high)
    return False


def selected_overlays(pack_meta: dict, target_format: int = 121) -> list[str]:
    # Multiple overlays may apply simultaneously. Preserve declared order:
    # the broad 1.21.6 overlay is applied first, then the exact 26.3 overlay.
    entries = pack_meta.get("overlays", {}).get("entries", [])
    selected = [
        item["directory"] for item in entries
        if supports_format(item.get("formats"), target_format)
    ]
    if not selected:
        raise AssertionError(
            f"No Minecraft {target_format} overlay found in publisher pack")
    return selected


def logical_pack_files(
    archive: zipfile.ZipFile, overlays: list[str]
) -> dict[str, tuple[int, bytes, str]]:
    """Map logical paths to (overlay priority, bytes, archive path)."""
    result: dict[str, tuple[int, bytes, str]] = {}
    priorities = {directory.rstrip("/") + "/": index + 1
                  for index, directory in enumerate(overlays)}
    for info in archive.infolist():
        name = info.filename
        if info.is_dir():
            continue
        priority = 0
        logical = name
        for prefix, value in priorities.items():
            if name.startswith(prefix):
                priority = value
                logical = name[len(prefix):]
                break
        else:
            if re.match(r"^pack_[^/]+/", name):
                continue
        if not (logical.startswith("data/") or logical == "pack.mcmeta"):
            continue
        blob = archive.read(info)
        previous = result.get(logical)
        if previous is None or priority > previous[0]:
            result[logical] = (priority, blob, name)
        elif priority == previous[0] and blob != previous[1]:
            raise AssertionError(
                f"Conflicting same-priority overlay/base file for {logical}: "
                f"{previous[2]} vs {name}")
    return result

def parse_functions(files: dict[str, tuple[int, bytes, str]]) -> tuple[dict, dict]:
    function_candidates = {}
    tag_candidates = {}
    for logical, (overlay_priority, blob, archive_path) in files.items():
        function_match = FUNCTION_PATH.match(logical)
        tag_match = TAG_PATH.match(logical)
        if not function_match and not tag_match:
            continue
        # Minecraft 26.3 uses singular function/functions-tag directories.
        # Prefer the singular 26.3 path unless the selected overlay overrides it.
        singular_priority = 1 if "/function/" in logical or "/tags/function/" in logical else 0
        candidate_priority = (overlay_priority, singular_priority)
        if function_match:
            namespace, path = function_match.groups()
            function_id = f"{namespace}:{path}"
            previous = function_candidates.get(function_id)
            if previous and candidate_priority == previous[0] and blob != previous[1]:
                raise AssertionError(f"Conflicting function definitions for {function_id}")
            if previous is None or candidate_priority > previous[0]:
                function_candidates[function_id] = (candidate_priority, blob, archive_path)
        else:
            namespace, path = tag_match.groups()
            tag_id = f"{namespace}:{path}"
            previous = tag_candidates.get(tag_id)
            if previous and candidate_priority == previous[0] and blob != previous[1]:
                raise AssertionError(f"Conflicting function-tag definitions for {tag_id}")
            if previous is None or candidate_priority > previous[0]:
                tag_candidates[tag_id] = (candidate_priority, blob, archive_path)

    functions = {}
    for function_id, (_, blob, archive_path) in function_candidates.items():
        text = blob.decode("utf-8-sig")
        lines = text.splitlines()
        commands = [line.strip() for line in lines
                    if line.strip() and not line.lstrip().startswith("#")]
        direct_calls = []
        tag_calls = []
        scheduled_calls = []
        for line in commands:
            scheduled = SCHEDULE_CALL.findall(line)
            if scheduled:
                scheduled_calls.extend(scheduled)
                continue
            for match in FUNCTION_CALL.finditer(line):
                target = match.group(1)
                (tag_calls if target.startswith("#") else direct_calls).append(target)
        functions[function_id] = {
            "source": archive_path,
            "line_count": len(lines),
            "commands": len(commands),
            "execute": sum(line.startswith("execute ") for line in commands),
            "scoreboard": sum(line.startswith("scoreboard ") for line in commands),
            "data": sum(line.startswith("data ") for line in commands),
            "selectors": sum(len(re.findall(r"@[easpn]\b", line)) for line in commands),
            "summon": sum(line.startswith("summon ") for line in commands),
            "kill": sum(line.startswith("kill ") for line in commands),
            "tp": sum(line.startswith("tp ") for line in commands),
            "tag": sum(line.startswith("tag ") for line in commands),
            "function_calls": direct_calls,
            "function_tag_calls": tag_calls,
            "scheduled_calls": scheduled_calls,
            "command_preview": commands[:8],
        }

    tags = {}
    for tag_id, (_, blob, _) in tag_candidates.items():
        payload = json.loads(blob)
        values = []
        for item in payload.get("values", []):
            value = item if isinstance(item, str) else item.get("id")
            if value:
                values.append(value)
        tags[tag_id] = values
    return functions, tags

def build_reachable(functions: dict, tags: dict) -> dict:
    entrypoints = []
    unresolved_tags = set()
    for tag_id in ("minecraft:load", "minecraft:tick"):
        entrypoints.extend(tags.get(tag_id, []))

    edges: dict[str, set[str]] = {name: set() for name in functions}
    schedule_edges: dict[str, set[str]] = {name: set() for name in functions}
    for name, item in functions.items():
        for target in item["function_calls"] + item["scheduled_calls"]:
            if target in functions:
                edges[name].add(target)
        for tag in item["function_tag_calls"]:
            tag_id = tag[1:]
            values = tags.get(tag_id)
            if values is None:
                unresolved_tags.add(tag_id)
                continue
            for target in values:
                if target in functions:
                    edges[name].add(target)
        for target in item["scheduled_calls"]:
            if target in functions:
                schedule_edges[name].add(target)

    expanded_entries = []
    for entry in entrypoints:
        if entry.startswith("#"):
            values = tags.get(entry[1:])
            if values is None:
                unresolved_tags.add(entry[1:])
            else:
                expanded_entries.extend(values)
        else:
            expanded_entries.append(entry)
    entrypoints = expanded_entries

    reachable = set()
    pending = list(entrypoints)
    while pending:
        current = pending.pop()
        if current in reachable or current not in functions:
            continue
        reachable.add(current)
        pending.extend(edges[current] - reachable)

    def can_reach(source: str, target: str) -> bool:
        seen = set()
        stack = [source]
        while stack:
            node = stack.pop()
            if node == target:
                return True
            if node in seen:
                continue
            seen.add(node)
            stack.extend(edges.get(node, set()) - seen)
        return False

    recurring_schedule_edges = []
    for source, targets in schedule_edges.items():
        for target in targets:
            if source in reachable and target in reachable and can_reach(target, source):
                recurring_schedule_edges.append({"from": source, "to": target})

    return {
        "entrypoints": sorted(set(entrypoints)),
        "reachable_functions": sorted(reachable),
        "unresolved_function_tags": sorted(unresolved_tags),
        "recurring_schedule_edges": recurring_schedule_edges,
        "edges": {name: sorted(targets) for name, targets in edges.items()
                  if name in reachable},
        "scheduled_edges": {name: sorted(targets) for name, targets in schedule_edges.items()
                            if name in reachable},
    }


def census(pack_path: Path = PACK) -> dict:
    OUT.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(pack_path) as archive:
        names = set(archive.namelist())
        if "pack.mcmeta" not in names:
            raise AssertionError("Publisher archive lacks pack.mcmeta")
        meta = json.loads(archive.read("pack.mcmeta"))
        overlays = selected_overlays(meta)
        files = logical_pack_files(archive, overlays)
        functions, tags = parse_functions(files)
    graph = build_reachable(functions, tags)
    reachable = graph["reachable_functions"]
    ranked = sorted(
        ({"function": name, **functions[name]} for name in reachable),
        key=lambda row: (row["commands"], row["execute"], row["selectors"]),
        reverse=True,
    )
    report = {
        "milestone": "COMPILER-IR-032-GATE-A",
        "status": "accepted_exact_publisher_static_tick_census",
        "publisher_sha256": PACK_SHA256,
        "version_id": VERSION_ID,
        "filename": FILENAME,
        "target_minecraft_data_pack_format": 121,
        "selected_overlays": overlays,
        "root_pack_format": meta.get("pack", {}).get("pack_format"),
        "total_archive_entries": len(names),
        "function_count": len(functions),
        "function_tag_count": len(tags),
        "reachable_function_count": len(reachable),
        "entrypoints": graph["entrypoints"],
        "unresolved_function_tags": graph["unresolved_function_tags"],
        "recurring_schedule_edges": graph["recurring_schedule_edges"],
        "reachable_call_graph": graph["edges"],
        "reachable_schedule_graph": graph["scheduled_edges"],
        "top_reachable_functions_by_static_command_count": ranked[:30],
        "static_not_dynamic": True,
        "cpu_hot_path_proven": False,
        "optimizer_implemented": False,
        "function_call_frequency_inferred": False,
    }
    (OUT / "inventory.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# IR-032 exact Dynamic Lights source census",
        "",
        f"- Publisher SHA-256: {PACK_SHA256}",
        f"- Version ID: {VERSION_ID}",
        f"- Applied 26.3 overlays in order: {", ".join(overlays)}",
        f"- Function files: {len(functions)}",
        f"- Reachable functions: {len(reachable)}",
        f"- Entry points: {', '.join(graph['entrypoints'])}",
        f"- Recurring scheduled edges: {json.dumps(graph['recurring_schedule_edges'])}",
        "",
        "## Highest static command counts among reachable functions",
        "",
        "| Function | Commands | Execute | Scoreboard | Data | Selector tokens | Function calls |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for row in ranked[:30]:
        lines.append(
            f"| {row['function']} | {row['commands']} | {row['execute']} | "
            f"{row['scoreboard']} | {row['data']} | {row['selectors']} | "
            f"{len(row['function_calls']) + len(row['function_tag_calls']) + len(row['scheduled_calls'])} |"
        )
    lines.extend([
        "",
        "**Interpretation:** these are static source counts and call-graph reachability only. "
        "They do not establish dynamic invocation frequency, CPU cost, or an optimization opportunity.",
        "",
    ])
    (OUT / "source-census.md").write_text("\n".join(lines), encoding="utf-8")
    print("IR032_SOURCE_CENSUS " + json.dumps({
        "status": report["status"],
        "sha256": PACK_SHA256,
        "overlays": overlays,
        "functions": len(functions),
        "reachable": len(reachable),
        "entrypoints": graph["entrypoints"],
        "recurring_schedule_edges": graph["recurring_schedule_edges"],
        "top_functions": [row["function"] for row in ranked[:8]],
    }, sort_keys=True), flush=True)
    return report


def main() -> None:
    fetched = fetch_pinned_pack()
    report = census()
    report["fetch"] = fetched
    (OUT / "inventory.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
