"""IR-030 exact-source coordinate-read site-count parser."""
from __future__ import annotations

import re

SITE_ROW = re.compile(r"FC_IR030_SITE_ROW axis=([xyz]) calls=(\d+)")
EXPECTED_SITE_CALLS = {"x": 1940, "y": 1940, "z": 1940}


def parse_site_rows(text: str) -> dict[str, int]:
    rows: dict[str, int] = {}
    for line in text.splitlines():
        match = SITE_ROW.search(line)
        if match is None:
            continue
        axis, raw_calls = match.groups()
        if axis in rows:
            raise ValueError(f"Duplicate IR030 site row for axis {axis}")
        rows[axis] = int(raw_calls)
    if set(rows) != set(EXPECTED_SITE_CALLS):
        raise ValueError(f"Incomplete IR030 site census: {rows!r}")
    for axis, expected in EXPECTED_SITE_CALLS.items():
        if rows[axis] != expected:
            raise ValueError(
                f"IR030 {axis} source-site exposure drift: "
                f"observed {rows[axis]}, expected {expected}")
    if sum(rows.values()) != 5820:
        raise ValueError(f"IR030 site counts do not sum to 5820: {rows!r}")
    return rows
