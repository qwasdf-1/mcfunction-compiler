#!/usr/bin/env python3
"""PERF-012: Macro region compilation benchmark on Minecraft 26.3."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import statistics
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from run_compatibility_probe import (
    free_port,
    locate_official_server_jar,
    start_server,
    wait_for_rcon,
    write_server_files,
    command,
)

os.environ["FC_FUNCTION_TIMING"] = "true"

REPORT_DIR = ROOT / "build" / "benchmarks" / "PERF-012"
INVOCATIONS = 300


def run_benchmark_for_mode(mode: str, server_jar: Path, run_id: str) -> dict[str, object]:
    work = ROOT / "run" / f"macro-perf-{run_id}-{mode}"
    if work.exists():
        shutil.rmtree(work)
    work.mkdir(parents=True)
    port = free_port()
    write_server_files(work, port, include_modded_command=False)
    log_path = REPORT_DIR / f"{run_id}-{mode}.server.log"
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    process, _ = start_server(mode, work, server_jar, log_path)
    client = None
    latencies_ms: list[float] = []
    final_score = None
    status_before = ""
    status_after = ""

    try:
        client = wait_for_rcon(process, port)
        command(client, "scoreboard objectives add fc_probe dummy")
        command(client, "scoreboard players reset #mb_acc fc_probe")
        command(client, "scoreboard players reset #mb_temp fc_probe")

        # Warmup
        for i in range(10):
            command(client, f"function function_compiler_probe:macro_bench_workload {{init:{i},step:2,sub:1}}")

        if mode != "vanilla":
            status_before = command(client, "function_compiler_probe status")

        # Measured invocations with tuple repetition and variation
        for i in range(INVOCATIONS):
            init = (i % 8) * 10
            t0 = time.perf_counter()
            command(client, f"function function_compiler_probe:macro_bench_workload {{init:{init},step:5,sub:2}}")
            t1 = time.perf_counter()
            latencies_ms.append((t1 - t0) * 1000.0)

        resp = command(client, "scoreboard players get #mb_acc fc_probe")
        match = re.search(r"has (-?\d+)", resp)
        if match:
            final_score = int(match.group(1))

        if mode != "vanilla":
            status_after = command(client, "function_compiler_probe status")

    finally:
        if client:
            try:
                command(client, "stop")
            except Exception:
                pass
            client.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except Exception:
            process.kill()
        if work.exists():
            shutil.rmtree(work, ignore_errors=True)

    latencies_ms.sort()
    mean_lat = statistics.mean(latencies_ms)
    median_lat = statistics.median(latencies_ms)
    p95_lat = latencies_ms[int(len(latencies_ms) * 0.95)]

    server_timed_calls = 0
    server_elapsed_nanos = 0
    if status_after:
        if m := re.search(r"function_timed_calls=(\d+)", status_after):
            server_timed_calls = int(m.group(1))
        if m := re.search(r"function_elapsed_nanos=(\d+)", status_after):
            server_elapsed_nanos = int(m.group(1))

    return {
        "mode": mode,
        "invocations": INVOCATIONS,
        "mean_ms": round(mean_lat, 4),
        "median_ms": round(median_lat, 4),
        "p95_ms": round(p95_lat, 4),
        "server_timed_calls": server_timed_calls,
        "server_elapsed_nanos": server_elapsed_nanos,
        "server_avg_us": round(server_elapsed_nanos / server_timed_calls / 1000.0, 2) if server_timed_calls else 0.0,
        "final_score": final_score,
        "status_before": status_before,
        "status_after": status_after,
    }


def main() -> int:
    server_jar = locate_official_server_jar()
    run_id = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    print(f"Running PERF-012 Macro Benchmark (run_id={run_id})...")

    print("Running mode: fabric-off (vanilla queue)...")
    baseline = run_benchmark_for_mode("fabric-off", server_jar, run_id)
    print(f"  fabric-off: median={baseline['median_ms']}ms, P95={baseline['p95_ms']}ms")

    print("Running mode: fabric-on (unfused wrapper queue)...")
    wrapper_on = run_benchmark_for_mode("fabric-on", server_jar, run_id)
    print(f"  fabric-on: median={wrapper_on['median_ms']}ms, server_avg={wrapper_on['server_avg_us']}us")

    print("Running mode: fused-interpreted (macro fused regions)...")
    candidate = run_benchmark_for_mode("fused-interpreted", server_jar, run_id)
    print(f"  fused-interpreted: median={candidate['median_ms']}ms, server_avg={candidate['server_avg_us']}us")

    print("Running mode: bytecode-emitted (parameterized macro bytecode)...")
    bytecode = run_benchmark_for_mode("bytecode-emitted", server_jar, run_id)
    print(f"  bytecode-emitted: median={bytecode['median_ms']}ms, server_avg={bytecode['server_avg_us']}us")

    # Differential parity check
    if (
        baseline["final_score"] != candidate["final_score"]
        or baseline["final_score"] != wrapper_on["final_score"]
        or baseline["final_score"] != bytecode["final_score"]
    ):
        print(f"ERROR: Final score mismatch! baseline={baseline['final_score']}, candidate={candidate['final_score']}, bytecode={bytecode['final_score']}")
        return 1

    speedup_median = (baseline["median_ms"] - candidate["median_ms"]) / baseline["median_ms"] * 100.0
    speedup_mean = (baseline["mean_ms"] - candidate["mean_ms"]) / baseline["mean_ms"] * 100.0
    queue_speedup = 0.0
    if wrapper_on["server_avg_us"] > 0 and candidate["server_avg_us"] > 0:
        queue_speedup = (wrapper_on["server_avg_us"] - candidate["server_avg_us"]) / wrapper_on["server_avg_us"] * 100.0

    bc_speedup_median = (baseline["median_ms"] - bytecode["median_ms"]) / baseline["median_ms"] * 100.0
    bc_speedup_mean = (baseline["mean_ms"] - bytecode["mean_ms"]) / baseline["mean_ms"] * 100.0
    bc_queue_speedup = 0.0
    if wrapper_on["server_avg_us"] > 0 and bytecode["server_avg_us"] > 0:
        bc_queue_speedup = (wrapper_on["server_avg_us"] - bytecode["server_avg_us"]) / wrapper_on["server_avg_us"] * 100.0

    print(f"Score parity verified across all 4 modes: score={baseline['final_score']}")
    print(f"Fused-interpreted median improvement: {speedup_median:+.2f}%")
    print(f"Fused-interpreted mean improvement: {speedup_mean:+.2f}%")
    print(f"Bytecode-emitted median improvement: {bc_speedup_median:+.2f}%")
    print(f"Bytecode-emitted mean improvement: {bc_speedup_mean:+.2f}%")
    if queue_speedup:
        print(f"Fused server queue latency improvement: {queue_speedup:+.2f}%")
    if bc_queue_speedup:
        print(f"Bytecode server queue latency improvement: {bc_queue_speedup:+.2f}%")

    report = {
        "benchmark": "PERF-012-MACRO-REGION-COMPILATION",
        "run_id": run_id,
        "invocations": INVOCATIONS,
        "baseline": baseline,
        "wrapper_on": wrapper_on,
        "candidate": candidate,
        "bytecode": bytecode,
        "speedup_median_percent": round(speedup_median, 2),
        "speedup_mean_percent": round(speedup_mean, 2),
        "queue_speedup_percent": round(queue_speedup, 2),
        "bytecode_speedup_median_percent": round(bc_speedup_median, 2),
        "bytecode_speedup_mean_percent": round(bc_speedup_mean, 2),
        "bytecode_queue_speedup_percent": round(bc_queue_speedup, 2),
    }

    report_path = REPORT_DIR / f"macro-benchmark-{run_id}.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Report written to {report_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
