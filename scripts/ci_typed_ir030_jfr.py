#!/usr/bin/env python3
"""IR-030 Gate B: original publisher JFR ExecutionSample attribution, not an A/B speedup.

Two fresh Java25 / Minecraft26.3 Fabric compiler-OFF events. All read/write
categories are inclusive stack presence and may overlap. No compiler feature,
gameplay commands or original publisher sources are changed.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "build/reports/COMPILER-IR-030-JFR"
VEIN = ROOT / "build/benchmarks/PERF-011-veinminer"
PACK = ROOT / "references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
PIN = "fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS = ("original_1", "original_2")
MIN_SAMPLES = 200

def frame(frame: dict) -> tuple[str, str]:
    method = frame.get("method") or {}
    typ = method.get("type") or {}
    return (str(typ.get("name") or "").replace("/", "."),
            str(method.get("name") or ""))

def category_samples(identities: list[tuple[str, str]]) -> set[str]:
    def has(class_suffix: str, method: str) -> bool:
        return any(c.endswith(class_suffix) and m == method for c, m in identities)
    read = (has(".DataCommands", "getSingleTag")
            or has(".DataCommands", "getData")
            or has(".DataCommands", "getNumeric"))
    store = has(".ExecuteCommand", "lambda$storeData$0")
    serialize = (has(".EntityDataAccessor", "getData")
                 or has(".NbtPredicate", "getEntityTagToCompare")
                 or has(".Entity", "saveWithoutId"))
    selected = set()
    if read:
        selected.add("read_command")
    if store:
        selected.add("outer_store_callback")
    if serialize:
        selected.add("entity_serialization")
    if read and serialize:
        selected.add("read_with_serialization")
    if store and serialize:
        selected.add("store_with_serialization")
    if has(".DataCommands", "getSingleTag"):
        selected.add("single_nbt_path_get")
    if has(".NbtPathArgument$NbtPath", "get"):
        selected.add("nbt_path_get")
    if has(".NbtPathArgument$NbtPath", "set"):
        selected.add("nbt_path_set")
    if has(".EntityDataAccessor", "setData"):
        selected.add("entity_set_data")
    if has(".Entity", "load"):
        selected.add("entity_load")
    if has(".Entity", "saveWithoutId"):
        selected.add("entity_save_without_id")
    return selected

def summarize_events(events: list[dict], tid: int) -> dict:
    server = []
    for event in events:
        if event.get("type") != "jdk.ExecutionSample":
            continue
        values = event.get("values") or {}
        thread = values.get("sampledThread") or {}
        if str(thread.get("osThreadId", "")) != str(tid):
            continue
        server.append(values)
    runnable = [v for v in server if v.get("state") == "STATE_RUNNABLE"]
    if len(runnable) < MIN_SAMPLES:
        raise AssertionError(f"Only {len(runnable)} runnable Minecraft Server-thread samples")
    counts = Counter()
    leaves = Counter()
    read_leaves = Counter()
    store_leaves = Counter()
    for values in runnable:
        frames = (values.get("stackTrace") or {}).get("frames") or []
        stack = [frame(item) for item in frames]
        if not stack:
            continue
        kinds = category_samples(stack)
        for name in kinds:
            counts[name] += 1
        name = ".".join(stack[0])
        leaves[name] += 1
        if "read_command" in kinds:
            read_leaves[name] += 1
        if "outer_store_callback" in kinds:
            store_leaves[name] += 1
    n = len(runnable)
    result = {
        "server_thread_tid": tid,
        "server_thread_execution_samples": len(server),
        "server_thread_runnable_samples": n,
        "server_thread_nonrunnable_samples": len(server) - n,
        "counts_inclusive": dict(counts),
        "fractions_inclusive": {k: counts[k] / n for k in (
            "read_command", "outer_store_callback", "entity_serialization",
            "read_with_serialization", "store_with_serialization",
            "single_nbt_path_get", "nbt_path_get", "nbt_path_set",
            "entity_set_data", "entity_load", "entity_save_without_id")},
        "top_server_leaf_frames": leaves.most_common(15),
        "top_read_leaf_frames": read_leaves.most_common(12),
        "top_store_leaf_frames": store_leaves.most_common(12),
        "fraction_categories_overlap": True,
        "capture": "jdk.ExecutionSample runnable Server-thread only",
        "not_a_cpu_speedup_or_avoidable_work_estimate": True,
    }
    if counts["read_command"] == 0 and counts["outer_store_callback"] == 0:
        raise AssertionError("Neither original inner getter nor original outer store sampled")
    return result

def analyze_jfr(path: Path, tid: int) -> dict:
    cmd = ["jfr", "print", "--json", "--events", "jdk.ExecutionSample",
           "--stack-depth", "128", str(path)]
    r = subprocess.run(cmd, text=True, capture_output=True, timeout=180, check=False)
    if r.returncode:
        raise RuntimeError(f"JFR extraction failed: {r.stderr[-1500:]}")
    data = json.loads(r.stdout)
    events = data.get("recording", {}).get("events")
    if not isinstance(events, list):
        raise AssertionError("Unexpected JFR recording.events schema")
    result = summarize_events(events, tid)
    result["jfr_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    result["all_thread_execution_events"] = len(events)
    return result

def run_original(label: str) -> dict:
    existing = set(VEIN.glob("vein-*/results.json"))
    stage = OUT / f"{label}-premining.json"
    env = dict(os.environ)
    env.pop("GRADLE_RO_DEP_CACHE", None)
    env["GRADLE_USER_HOME"] = str(ROOT / "build/gradle-cache-ir030-jfr")
    for k in list(env):
        if (k.startswith("FC_CPU") or k.startswith("FC_MACRO")
                or k.startswith("FC_COMPILER_") or k.startswith("FC_TYPED_IR_")
                or k.startswith("FC_COMMAND_CALLBACK")):
            env.pop(k, None)
    cmd = [
        sys.executable, str(ROOT / "scripts/run_veinminer_profile.py"),
        "--stack", "fabric", "--compiler-mode", "off", "--side", "6",
        "--capture-timeout", "150", "--no-spark", "--capture-server-thread-cpu",
        "--capture-jfr-execution", "--tick-stability-diagnostics",
        "--pre-event-idle-seconds", "9",
        "--setup-rcon-timeout-seconds", "45",
        "--startup-readiness-record", str(stage),
    ]
    try:
        proc = subprocess.run(cmd, cwd=ROOT, env=env, text=True,
                              capture_output=True, timeout=850, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{label}: runner process deadline, no event retry") from exc
    (OUT / f"{label}-stdout.log").write_text(proc.stdout, encoding="utf-8")
    (OUT / f"{label}-stderr.log").write_text(proc.stderr, encoding="utf-8")
    if proc.returncode:
        raise RuntimeError(f"{label}: native event failed {proc.returncode}: {proc.stderr[-1800:]}")
    new = set(VEIN.glob("vein-*/results.json")) - existing
    if len(new) != 1:
        raise AssertionError(f"{label}: expected one newly recorded original event, got {len(new)}")
    path = new.pop()
    manifest = json.loads(path.read_text(encoding="utf-8"))
    cpu = manifest.get("server_thread_event_cpu") or {}
    if (not manifest.get("valid_native_workload")
            or manifest.get("datapack_sha256") != PIN
            or manifest.get("queue_head_delta") != 1952
            or manifest.get("work_after") != 215
            or manifest.get("run_state_after") != 0
            or manifest.get("event_timeout_reached")
            or manifest.get("compiler_mode") != "off"
            or manifest.get("jfr_profile_kind") != "execution_sample"
            or not manifest.get("jfr_execution_capture_enabled")
            or manifest.get("jfr_cpu_capture_enabled")
            or not manifest.get("tick_pre_event_stability", {}).get("stable")
            or not cpu.get("cpu_measurement_valid")
            or not cpu.get("host_quality_pass")
            or cpu.get("server_thread_cpu_running_ns", 0) <= 0):
        raise AssertionError(f"{label}: original gameplay/JFR/host parity gates failed")
    recording = ROOT / manifest["jfr_cpu_profile_path"]
    if not recording.is_file():
        raise AssertionError(f"{label}: JFR recording missing")
    shutil.copy2(recording, OUT / f"{label}.jfr")
    result = analyze_jfr(recording, int(cpu["server_thread_tid"]))
    return {
        "label": label, "manifest_path": str(path.relative_to(ROOT)),
        "original_publisher_sha256": PIN,
        "work_completed": 215, "queue_steps": 1952,
        "server_cpu_ns_descriptive": cpu["server_thread_cpu_running_ns"],
        "host_quality": cpu["host_quality_pass"],
        "jfr": result,
        "optimizations_disabled": True,
        "native_semantics_not_modified": True,
        "speedup_measured": False,
    }

def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    if not PACK.is_file() or hashlib.sha256(PACK.read_bytes()).hexdigest() != PIN:
        raise AssertionError("Original publisher archive SHA mismatch")
    report = {
        "milestone": "COMPILER-IR-030-GATE-B",
        "status": "started",
        "experimental_design": "two independent original compiler-off JFR description only",
        "cpu_optimization_or_speedup_claim": False,
        "results": {},
    }
    target = OUT / "results.json"
    try:
        for label in ARMS:
            report["results"][label] = run_original(label)
            target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print("IR030_JFR_ARM " + json.dumps({
                "label": label,
                "jfr": report["results"][label]["jfr"]["fractions_inclusive"],
                "samples": report["results"][label]["jfr"]["server_thread_runnable_samples"],
            }), flush=True)
        report["status"] = "accepted_descriptive"
    except Exception as exc:
        report["status"] = "invalid"
        report["error"] = repr(exc)
        raise
    finally:
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__":
    main()
