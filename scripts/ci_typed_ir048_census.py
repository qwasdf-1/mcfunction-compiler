#!/usr/bin/env python3
"""IR048 phase A: historical source-site join and fresh native cardinality census.

No compiler behavior changes or timing claims; the observer exists only in the
fixture build and never replaces a native modifier or terminal.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

from run_specialization_inventory import split_tokens

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-048-CENSUS"
CENSUS = ROOT / "tests/fixtures/compiler/ir042-census.json"
CENSUS_SHA = "5977367281d9c0958f5dbc3cabb7d22c65902373f71cf1871893a68d14c820a9"
ID = re.compile(r"[a-z0-9_.-]+:[a-z0-9_./-]+")
H = r"(?:#[A-Za-z0-9_.+\-]+|@s)"
O = r"[A-Za-z0-9_.+\-]+"
I = r"-?\d+"
R = rf"(?:{I}(?:\.\.(?:{I})?)?|\.\.{I})"
P = re.compile(rf"(?:if|unless) score {H} {O} (?:matches {R}|(?:=|<=|>=|<|>) {H} {O})")


def shape(line):
    if "$(" in line:
        return None
    tokens = split_tokens(line)
    if len(tokens) < 6 or tokens[0] != "execute" or tokens[-3:-1] != ["run", "function"] or not ID.fullmatch(tokens[-1]):
        return None
    prefix = tokens[1:-3]
    # Only the observed sequences. A selector is one token, including
    # quoted/bracketed arguments. Native parsing, not this screen, decides legality.
    def selector(token):
        return bool(re.fullmatch(r"@[aesprn](?:\[.*\])?", token))
    if len(prefix) == 4 and prefix[0] == "as" and selector(prefix[1]) and prefix[2:] == ["at", "@s"]:
        return "as_at"
    if len(prefix) > 4 and prefix[-4] == "as" and selector(prefix[-3]) and prefix[-2:] == ["at", "@s"] and P.fullmatch(" ".join(prefix[:-4])):
        return "score_as_at"
    if len(prefix) > 2 and prefix[0] == "as" and selector(prefix[1]) and P.fullmatch(" ".join(prefix[2:])):
        return "as_score"
    return None


def join(census, pack):
    seen = set()
    sites = []
    all_inputs = Counter(line for lines in pack.functions.values() for line in lines)
    total = 0
    for row in census["rows"]:
        fid, index = row["function"], int(row["index"])
        if (fid, index) in seen or fid not in census["target_functions"]:
            raise AssertionError("duplicate or unexpected source row")
        seen.add((fid, index))
        line = pack.functions[fid][index]
        if row["input"] != line[:240]:
            raise AssertionError("frozen source mismatch")
        visits = int(row["entries"])
        total += visits
        kind = shape(line)
        if kind is not None:
            sites.append({"function": fid, "index": index, "input": line, "shape": kind,
                          "historical_visits": visits, "historical_ordinary_callbacks": int(row["callbacks"]),
                          "publisher_identical_text_sites": all_inputs[line]})
    for fid in census["target_functions"]:
        if sum(f == fid for f, _ in seen) != len(pack.functions[fid]):
            raise AssertionError("incomplete historical source join")
    assert len(seen) == 347 and total == 257697
    sites.sort(key=lambda s: (s["function"], s["index"]))
    expected = {"as_at": (4, 1963), "score_as_at": (1, 601), "as_score": (2, 3)}
    actual = {k: (sum(s["shape"] == k for s in sites),
                  sum(s["historical_visits"] for s in sites if s["shape"] == k))
              for k in expected}
    assert actual == expected, actual
    for i, site in enumerate(sites):
        site["id"] = i
    return sites


def parse_log(raw, sites):
    assert raw.count("IR048_CENSUS_BEGIN") == 1 and raw.count("IR048_CENSUS_END invalid=0") == 1, "missing or invalid bounded census"
    registered = {}
    for m in re.finditer(r"IR048_REGISTER id=(\d+) function=(\S+) index=(\d+)", raw):
        idx, fid, index = m.groups()
        idx = int(idx)
        assert idx not in registered
        registered[idx] = (fid, int(index))
    assert registered == {s["id"]: (s["function"], s["index"]) for s in sites}, registered
    pattern = r"IR048_SITE id=(\d+) builds=(\d+) terminals=(\d+)"
    rows = {}
    for m in re.finditer(pattern, raw):
        idx, builds, terminals = map(int, m.groups())
        assert idx not in rows and 0 <= idx < len(sites)
        rows[idx] = {"builds": builds, "terminal_invocations": terminals, "stages": {}}
    assert set(rows) == set(range(len(sites))), rows
    pattern = r"IR048_STAGE id=(\d+) key=(\S+) calls=(\d+) returns=(\d+) outputs=(\d+) max_outputs=(\d+) forked_calls=(\d+)"
    for m in re.finditer(pattern, raw):
        idx, key, *counts = m.groups()
        idx = int(idx)
        stage = dict(zip(("calls", "returns", "outputs", "max_outputs", "forked_calls"), map(int, counts)))
        assert key not in rows[idx]["stages"]
        assert stage["returns"] <= stage["calls"] and stage["forked_calls"] <= stage["calls"]
        assert stage["outputs"] <= stage["returns"] * stage["max_outputs"]
        rows[idx]["stages"][key] = stage
    assert sum(r["builds"] for r in rows.values()) > 0
    # A site can legitimately be empty (e.g. @a on the original headless scene).
    # Do not infer completed child tasks from terminal invocation counts.
    return [site | {"fresh_native": rows[site["id"]]} for site in sites]


class CensusClient:
    """Adapt the existing event oracle's census start/stop protocol, not the event."""
    def __init__(self, client):
        self.client = client

    def command(self, command):
        return self.client.command({
            "functioncompiler exec-census-start": "fc_ir048_census start",
            "functioncompiler exec-census-stop": "fc_ir048_census stop",
        }.get(command, command))


def main():
    import ci_typed_ir042_publisher as pub
    from ci_typed_ir013 import stop
    OUT.mkdir(parents=True, exist_ok=True)
    raw = CENSUS.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == CENSUS_SHA, "historical fixture changed"
    census = json.loads(raw)
    publisher = pub.base.original_publisher()
    pack = pub.Pack("blastback", pub.base.PACK, pub.base.PIN)
    sites = join(census, pack)
    report = {"status": "started", "historical_fixture_sha256": CENSUS_SHA, "publisher": publisher,
              "sites": sites, "runtime_changed": False, "performance_claim": False}
    def save():
        (OUT / "results.json").write_text(json.dumps(report, indent=2) + "\n")
    save()
    original_options = pub.options
    pub.OUT = OUT
    pub.MODE = "native"
    pub.CENSUS = False
    pub.DIAGNOSTIC = False
    pub.SELECTED = None
    def options(mode):
        return original_options(mode) | {
            "FC_WRAPPER_PROBE": "false", "FC_TYPED_COMPILER_PROFILE": "",
            "FC_TYPED_IR_MODE": "", "FC_IR048_CENSUS": "true",
            "FC_IR048_CENSUS_SITES": "\n".join(f"{s['function']}\t{s['index']}\t{s['input']}" for s in sites),
        }
    pub.base.OUT = OUT
    pub.base.options = options
    try:
        proc, client, log = pub.base.launch("ir048-native")
        try:
            report["event"] = pub.event(CensusClient(client), label="ir048-native", census=True)
            assert report["event"]["state"] == census["event"]["state"], "restoration oracle mismatch"
        finally:
            stop(proc, client, log)
        report["sites"] = parse_log((OUT / "ir048-native.server.log").read_text(errors="replace"), sites)
        report["status"] = "observed"
        print("IR048_CENSUS_SUMMARY " + json.dumps({"status": report["status"], "sites": report["sites"]}), flush=True)
    except BaseException as exc:
        report.update(status="invalid", error=repr(exc))
        raise
    finally:
        save()


if __name__ == "__main__":
    main()
