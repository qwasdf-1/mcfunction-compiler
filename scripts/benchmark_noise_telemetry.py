"""Reusable Linux/JVM noise telemetry for Minecraft benchmarking.

OBSERVATIONS, not automatic corrections: CPU scheduling wait and Java JIT/GC
work can also change the server thread's own running-time cost via caches,
frequency, and compilation decisions. Do not subtract them from benchmark CPU
numbers or silently omit windows based on these counters.

Read /proc snapshots outside the core timed function to avoid attributing
the sampler itself to the reported timed server-thread CPU counter.
"""
from __future__ import annotations

import os
from pathlib import Path
import time


def _proc_cpu_ns(pid: int) -> int | None:
    try:
        data = (Path("/proc") / str(pid) / "stat").read_text()
        fields = data.rsplit(")", 1)[1].split()
        ticks = int(fields[11]) + int(fields[12])
        return round(ticks * 1_000_000_000 / os.sysconf("SC_CLK_TCK"))
    except (OSError, ValueError, IndexError):
        return None


def _thread_cpu_ns(pid: int) -> dict[str, dict]:
    tasks = Path("/proc") / str(pid) / "task"
    threads = {}
    try:
        paths = list(tasks.iterdir())
    except OSError:
        return threads
    for task in paths:
        if not task.name.isdecimal():
            continue
        try:
            name = (task / "comm").read_text().strip()
            sched = (task / "schedstat").read_text().split()
            if len(sched) < 2:
                continue
            threads[task.name] = {
                "name": name,
                "running_ns": int(sched[0]),
                "waiting_ns": int(sched[1]),
            }
        except (OSError, ValueError, IndexError):
            continue
    return threads


def _cgroup_cpu() -> dict[str, int]:
    path = Path("/sys/fs/cgroup/cpu.stat")
    if not path.exists():
        return {}
    result = {}
    try:
        for line in path.read_text().splitlines():
            fields = line.split()
            if len(fields) == 2:
                result[fields[0]] = int(fields[1])
    except (OSError, ValueError):
        pass
    return result


def _cpu_pressure_us() -> dict[str, int]:
    path = Path("/proc/pressure/cpu")
    if not path.exists():
        return {}
    result = {}
    try:
        for line in path.read_text().splitlines():
            parts = line.split()
            total = next((word for word in parts if word.startswith("total=")), None)
            if total is not None:
                result[parts[0]] = int(total.split("=", 1)[1])
    except (OSError, ValueError):
        pass
    return result


def snapshot_jvm_environment(pid: int) -> dict:
    affinity = None
    try:
        affinity = sorted(os.sched_getaffinity(pid))
    except (OSError, AttributeError):
        pass
    return {
        "monotonic_ns": time.monotonic_ns(),
        "jvm_process_cpu_ns": _proc_cpu_ns(pid),
        "jvm_threads": _thread_cpu_ns(pid),
        "loadavg_1m": os.getloadavg()[0],
        "cgroup_cpu": _cgroup_cpu(),
        "system_cpu_pressure_us": _cpu_pressure_us(),
        "process_affinity": affinity,
        "cpu_count": os.cpu_count(),
    }


def thread_role(name: str) -> str:
    """Linux comm names are truncated to 15 chars; categories are indicative."""
    name = name.lower()
    if "compiler" in name or name.startswith(("c1 ", "c2 ")):
        return "jit_compiler"
    if any(tag in name for tag in ("gc thread", "g1 ", "g1_", "zgc", "zworker",
                                   "shenandoah", "conc#")):
        return "gc"
    if name == "server thread":
        return "server"
    return "other_jvm"


def delta_environment(before: dict, after: dict) -> dict:
    if before["process_affinity"] != after["process_affinity"]:
        affinity_stable = False
    else:
        affinity_stable = True
    d = {
        "monitored_wall_ns": after["monotonic_ns"] - before["monotonic_ns"],
        "process_affinity": before["process_affinity"],
        "affinity_stable": affinity_stable,
        "load_before": before["loadavg_1m"],
        "load_after": after["loadavg_1m"],
    }
    proc0 = before["jvm_process_cpu_ns"]
    proc1 = after["jvm_process_cpu_ns"]
    d["whole_jvm_cpu_ns"] = (
        proc1 - proc0 if proc0 is not None and proc1 is not None else None
    )
    old_threads, new_threads = before["jvm_threads"], after["jvm_threads"]
    role_costs = {}
    role_wait = {}
    vanished = []
    for tid, t in old_threads.items():
        current = new_threads.get(tid)
        if current is None:
            vanished.append({"tid": tid, "name": t["name"]})
            continue
        if current["name"] != t["name"]:
            continue
        role = thread_role(t["name"])
        ns = current["running_ns"] - t["running_ns"]
        wait = current["waiting_ns"] - t["waiting_ns"]
        if ns < 0 or wait < 0:
            continue
        role_costs[role] = role_costs.get(role, 0) + ns
        role_wait[role] = role_wait.get(role, 0) + wait
    d["surviving_thread_running_ns_by_role"] = role_costs
    d["surviving_thread_wait_ns_by_role"] = role_wait
    d["threads_disappeared_during_window"] = vanished
    d["thread_accounting_incomplete"] = bool(vanished) or any(
        tid not in old_threads for tid in new_threads
    )
    # Process aggregate includes exited threads and is the more reliable
    # measure of entire JVM CPU, but has proc-stat tick granularity.
    for field in ("cgroup_cpu", "system_cpu_pressure_us"):
        d[field + "_delta"] = {
            k: new - before[field][k]
            for k, new in after[field].items()
            if k in before[field]
        }
    return d
