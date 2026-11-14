"""Linux Server-thread CPU accounting for opt-in native-event research.

Do not confuse the outer Gradle launcher PID with the Minecraft JVM. Find
the unique Server thread in the process tree, use Linux schedstat running-ns
and runqueue-wait accounting, and capture cgroup throttling as a host gate.
This module never changes Minecraft runtime behavior or installs an agent.
"""
from __future__ import annotations

from pathlib import Path
import re


def find_server_thread(launcher_pid: int, proc: Path = Path("/proc")) -> tuple[int,int]:
    if launcher_pid<=0:
        raise ValueError("Bad launcher PID")
    todo=[launcher_pid]
    visited=set()
    matches=[]
    while todo:
        pid=todo.pop()
        if pid in visited:
            continue
        visited.add(pid)
        tasks=proc/str(pid)/"task"
        if not tasks.is_dir():
            continue
        for task in tasks.iterdir():
            if not task.is_dir() or not task.name.isdigit():
                continue
            try:
                comm=(task/"comm").read_text().strip()
                if comm=="Server thread":
                    matches.append((pid,int(task.name)))
                children=(task/"children").read_text().split()
                todo.extend(int(child) for child in children if child.isdigit())
            except (OSError,ValueError):
                continue
    if len(set(matches))!=1:
        raise RuntimeError(
            f"Expected exactly one Minecraft Server thread beneath launcher "
            f"{launcher_pid}, found {matches}; visited={sorted(visited)[:40]}")
    return matches[0]


def read_thread_schedstat(pid: int, tid: int, proc: Path = Path("/proc")) -> dict:
    path=proc/str(pid)/"task"/str(tid)/"schedstat"
    values=path.read_text().split()
    if len(values)<3:
        raise RuntimeError(f"Invalid schedstat {path}: {values}")
    running,waiting,slices=map(int,values[:3])
    if running<=0 or waiting<0 or slices<=0:
        raise RuntimeError(f"Inactive or invalid Server thread schedstat: {values}")
    return {"pid":pid,"tid":tid,"cpu_running_ns":running,
            "runqueue_wait_ns":waiting,"timeslices":slices,
            "clock":"linux_schedstat_ns"}


def cgroup_throttle_count(path:Path=Path("/sys/fs/cgroup/cpu.stat"))->int|None:
    try:
        data=path.read_text()
    except OSError:
        return None
    match=re.search(r"(?m)^nr_throttled\s+(\d+)\s*$",data)
    return int(match.group(1)) if match is not None else None


def event_cpu_delta(before:dict,after:dict,
                    throttled_before:int|None,
                    throttled_after:int|None)->dict:
    if (before["pid"],before["tid"],before["clock"])!=(
            after["pid"],after["tid"],after["clock"]):
        raise AssertionError("Server-thread CPU clocks or thread IDs changed")
    cpu=after["cpu_running_ns"]-before["cpu_running_ns"]
    delay=after["runqueue_wait_ns"]-before["runqueue_wait_ns"]
    slices=after["timeslices"]-before["timeslices"]
    if cpu<=0 or delay<0 or slices<0:
        raise AssertionError("Server thread CPU counters regressed")
    throttled=(throttled_after-throttled_before
               if throttled_after is not None and throttled_before is not None
               else None)
    if throttled is not None and throttled<0:
        raise AssertionError("Cgroup throttle count regressed")
    wait_fraction=delay/(cpu+delay)
    return {
        "server_thread_cpu_running_ns":cpu,
        "server_thread_runqueue_wait_ns":delay,
        "server_thread_runqueue_wait_fraction":wait_fraction,
        "server_thread_timeslices":slices,
        "cgroup_nr_throttled_delta":throttled,
        "server_thread_pid":before["pid"],"server_thread_tid":before["tid"],
        "clock":before["clock"],
        "cpu_measurement_valid":True,
        "host_quality_pass":(
            throttled==0 and wait_fraction<=.25),
    }
