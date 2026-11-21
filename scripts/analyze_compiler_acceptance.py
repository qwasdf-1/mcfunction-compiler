#!/usr/bin/env python3
"""Parse the opt-in FC_ACCEPTANCE console census; no CPU/speedup claims."""
from __future__ import annotations

from collections import Counter
import re
from pathlib import Path

_ROW = re.compile(r"FC_ACCEPTANCE_ROW function=(\S+) outcome=(\S+) count=(\d+) input=(.*)$")
_BEGIN = re.compile(r"FC_ACCEPTANCE_BEGIN namespace=(\S+) events=(\d+) keys=(\d+)")
_END = re.compile(r"FC_ACCEPTANCE_END namespace=(\S+) events=(\d+)")


def parse_acceptance_log(path: Path) -> dict:
    lines = path.read_text(encoding="utf-8").splitlines()
    beginnings = [m for line in lines if (m := _BEGIN.search(line))]
    endings = [m for line in lines if (m := _END.search(line))]
    if len(beginnings) != 1 or len(endings) != 1:
        raise ValueError("Acceptance dump must contain exactly one begin/end marker")
    begin, end = beginnings[0], endings[0]
    namespace, total, unique = begin.group(1), int(begin.group(2)), int(begin.group(3))
    if end.group(1) != namespace or int(end.group(2)) != total:
        raise ValueError("Acceptance dump boundaries disagree")
    outcomes: Counter[str] = Counter()
    functions: dict[str, Counter[str]] = {}
    rows = []
    for line in lines:
        match = _ROW.search(line)
        if not match:
            continue
        function_id, outcome, count, command = match.groups()
        count = int(count)
        if count < 1 or (
            function_id != "<overflow>" and not function_id.startswith(namespace + ":")
        ):
            raise ValueError("Invalid acceptance count or unexpected function namespace")
        outcomes[outcome] += count
        functions.setdefault(function_id, Counter())[outcome] += count
        rows.append({
            "function": function_id, "outcome": outcome,
            "count": count, "input": command,
        })
    if len(rows) != unique or sum(outcomes.values()) != total:
        raise ValueError("Acceptance row count does not match begin/end controls")
    return {
        "namespace": namespace,
        "events": total,
        "unique_rows": unique,
        "outcomes": dict(sorted(outcomes.items())),
        "functions": {
            k: dict(sorted(v.items())) for k, v in sorted(functions.items())
        },
        "rows": rows,
    }
