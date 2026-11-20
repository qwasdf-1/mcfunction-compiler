#!/usr/bin/env python3
"""IR-015: acquire exactly two independently SHA-pinned publisher datapacks."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import urllib.request

from ci_typed_ir015_coverage import PINS

VERSIONS = {
    "veinminer": ("5jzz5SkG", "VeinMiner-5.3.0+26.3.zip"),
    "blastback": ("dMtA8r0n", "Blastback-Hotfix-3-26.3.zip"),
}


def fetch_bytes(url: str, *, maximum: int) -> bytes:
    req = urllib.request.Request(
        url, headers={"User-Agent": "MCFC-IR015-readonly-source-audit/1.0"})
    with urllib.request.urlopen(req, timeout=90) as response:
        blob = response.read(maximum + 1)
    if len(blob) > maximum:
        raise ValueError("Publisher response exceeds conservative download cap")
    return blob


def fetch(name: str) -> dict:
    version, filename = VERSIONS[name]
    metadata = json.loads(fetch_bytes(
        f"https://api.modrinth.com/v2/version/{version}", maximum=2_000_000))
    files = [f for f in metadata["files"] if f["filename"] == filename]
    if len(files) != 1:
        raise ValueError(f"Ambiguous/missing {name} publisher ZIP")
    data = fetch_bytes(files[0]["url"], maximum=80_000_000)
    observed = hashlib.sha256(data).hexdigest()
    pinned = PINS[name]["sha256"]
    if observed != pinned:
        raise ValueError(f"PIN MISMATCH {name}: {observed} expected {pinned}")
    target = Path(PINS[name]["path"])
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(data)
    return {"name": name, "publisher_version": version,
            "filename": filename, "sha256": observed, "bytes": len(data)}


if __name__ == "__main__":
    for item in VERSIONS:
        print("IR015_PINNED_SOURCE " + json.dumps(fetch(item)), flush=True)
