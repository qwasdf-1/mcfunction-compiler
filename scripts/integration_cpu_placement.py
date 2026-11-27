"""Controlled CPU placement for the Integration-001 qualification retry.

The Linux guest can enforce thread affinity, not physical hypervisor isolation.
Never use these observations to correct or omit a measured CPU window.
"""
from __future__ import annotations

import os
from pathlib import Path

CONTROL = None
SERVER = None
ROOT = Path("/sys/devices/system/cpu")

def read(path):
    try:
        return Path(path).read_text().strip()
    except OSError:
        return None

def parse_cpu_list(value):
    if not value:
        return set()
    result = set()
    for part in value.split(","):
        bounds = part.split("-")
        if len(bounds) == 1:
            result.add(int(bounds[0]))
        else:
            result.update(range(int(bounds[0]), int(bounds[1]) + 1))
    return result

def choose_affinity(allowed, siblings):
    allowed = set(allowed)
    if len(allowed) < 4:
        raise RuntimeError("controlled qualification requires at least four allowed logical CPUs")
    # Prefer the last logical CPU to avoid CPU0 housekeeping when possible.
    # Reserve all of its visible SMT siblings, not just the selected CPU.
    server = max(allowed)
    reserved = (set(siblings.get(server, (server,))) | {server}) & allowed
    rest = allowed - reserved
    if len(rest) < 2:
        raise RuntimeError("insufficient separate auxiliary CPUs")
    # Prefer separate visible cores before adding SMT siblings.
    first, extra, seen = [], [], set()
    for cpu in sorted(rest):
        if cpu in seen:
            extra.append(cpu)
        else:
            first.append(cpu)
            seen.update(siblings.get(cpu, (cpu,)))
    return server, sorted(reserved), sorted((first + extra)[:3])

def configure():
    global CONTROL
    allowed = sorted(os.sched_getaffinity(0))
    raw = {c:read(ROOT/f"cpu{c}/topology/thread_siblings_list") for c in allowed}
    siblings = {c:parse_cpu_list(raw[c]) or {c} for c in allowed}
    server, reserved, aux = choose_affinity(allowed, siblings)
    CONTROL = {"allowed_initial":allowed,"server_cpu":server,"reserved_visible_siblings":reserved,
               "auxiliary_cpus":aux,"visible_sibling_lists":raw,"active_processor_count":4,
               "isolation":"guest affinity only; external physical CPU/SMT isolation not guaranteed"}
    os.sched_setaffinity(0, set(aux))
    if os.sched_getaffinity(0) != set(aux):
        raise RuntimeError("controller affinity mismatch")
    return CONTROL

def bind_server(thread):
    global SERVER
    pid, tid = thread
    cpu = CONTROL["server_cpu"]
    # The launcher's children inherited the auxiliary mask. Move only the
    # actual Minecraft Server thread, after startup and before calibration.
    os.sched_setaffinity(tid, {cpu})
    if os.sched_getaffinity(tid) != {cpu}:
        raise RuntimeError("Server thread affinity mismatch")
    SERVER = (pid, tid)
    return {"pid":pid,"tid":tid,"affinity":sorted(os.sched_getaffinity(tid))}

def _cpu_times(cpu):
    for line in (read("/proc/stat") or "").splitlines():
        fields = line.split()
        if fields and fields[0] == f"cpu{cpu}":
            keys=("user","nice","system","idle","iowait","irq","softirq","steal","guest","guest_nice")
            return dict(zip(keys, map(int, fields[1:])))
    return {}

def snapshot(pid):
    if CONTROL is None:
        return None
    if SERVER is None or SERVER[0] != pid:
        raise RuntimeError("controlled snapshot before Server thread placement")
    _, tid = SERVER
    cpu = CONTROL["server_cpu"]
    task = Path(f"/proc/{pid}/task/{tid}")
    affinity = sorted(os.sched_getaffinity(tid))
    if affinity != [cpu]:
        raise RuntimeError("Server thread affinity changed during controlled run")
    stat=(read(task/"stat") or "").rsplit(")",1)[-1].split()
    last_cpu=int(stat[36]) if len(stat)>36 else None
    migrations=None
    for line in (read(task/"sched") or "").splitlines():
        if line.split(":",1)[0].strip()=="se.nr_migrations":
            migrations=int(line.split(":",1)[1].strip())
            break
    overlaps=[]
    for p in Path(f"/proc/{pid}/task").iterdir():
        if int(p.name)==tid:
            continue
        try:
            mask=os.sched_getaffinity(int(p.name))
        except ProcessLookupError:
            continue
        if mask.intersection(CONTROL["reserved_visible_siblings"]):
            overlaps.append({"tid":int(p.name),"name":read(p/"comm"),"affinity":sorted(mask)})
    freq={key:read(ROOT/f"cpu{cpu}/cpufreq"/key) for key in
          ("scaling_cur_freq","cpuinfo_cur_freq","scaling_governor","scaling_min_freq","scaling_max_freq")}
    return {"server_affinity":affinity,"last_cpu":last_cpu,"migrations":migrations,
            "auxiliary_overlap":overlaps,"frequency_sysfs":freq,"cpu_times_ticks":_cpu_times(cpu)}

def delta(before, after):
    if before is None or after is None:
        return None
    m0,m1=before["migrations"],after["migrations"]
    return {"before":before,"after":after,
            "server_migrations":m1-m0 if m0 is not None and m1 is not None else None,
            "cpu_times_ticks_delta":{k:v-before["cpu_times_ticks"][k] for k,v in
                after["cpu_times_ticks"].items() if k in before["cpu_times_ticks"]}}
