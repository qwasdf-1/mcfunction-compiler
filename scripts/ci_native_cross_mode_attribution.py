#!/usr/bin/env python3
"""SCHED-ATTR-002: native-command comparison across official vanilla, Fabric,
and Fabric + compiler installed but optimizations disabled.

All three arms execute identical ordinary .mcfunction text on production server
JARs. Linux /proc Server-thread CPU time is the primary *screening* measure;
RCON round-trip time and standalone JFR recordings are secondary. A single
GitHub-hosted runner carries the six-boot counterbalanced sequence.
This does not constitute a production promotion / precise attribution gate.
"""

from __future__ import annotations

from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import statistics
import subprocess
import sys
import time
import urllib.request
import zipfile

from ci_smoke_server import Rcon, unused_port, wait_for_rcon
from ci_scheduler_attribution import jcmd
from mc_harness.server_lifecycle import (
    MINECRAFT_SERVER_SHA256,
    locate_official_server_jar,
)

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "benchmarks" / "SCHED-ATTR-002"
FABRIC_BASE = OUTPUT / "fabric-install"
RUN_ROOT = ROOT / "run"
PACK = "fc_sched_cross_mode"
OBJECTIVE = "fc_sched"
HOLDER = "#x"
GATE = "#gate"
COMMANDS_PER_CALL = 2000
WARMUP_CALLS = 300
MEASURED_CALLS = 4000
JFR_DIAGNOSTIC_CALLS = 5000
MODES = ("vanilla", "fabric", "compiler", "compiler", "fabric", "vanilla")
FAMILIES = ("score", "condition_true", "condition_false")
FAMILY_ORDER = (
    ("score", "condition_true", "condition_false"),
    ("condition_true", "condition_false", "score"),
    ("condition_false", "score", "condition_true"),
    ("condition_true", "score", "condition_false"),
    ("condition_false", "condition_true", "score"),
    ("score", "condition_false", "condition_true"),
)
JVM_ARGS = ("-Xms512M", "-Xmx2G")
FABRIC_INSTALLER_VERSION = "1.1.2"
FABRIC_LOADER_VERSION = "0.20.1"
FABRIC_API_VERSION = "0.165.0+26.3"
FABRIC_INSTALLER_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-installer/"
    f"{FABRIC_INSTALLER_VERSION}/fabric-installer-{FABRIC_INSTALLER_VERSION}.jar"
)
FABRIC_API_URL = (
    "https://maven.fabricmc.net/net/fabricmc/fabric-api/fabric-api/"
    f"{FABRIC_API_VERSION}/fabric-api-{FABRIC_API_VERSION}.jar"
)
REPORT = OUTPUT / "results.json"


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def find_production_jar() -> Path:
    choices = []
    for candidate in (ROOT / "build" / "libs").glob("function-compiler-*.jar"):
        if "sources" in candidate.name or "dev" in candidate.name:
            continue
        with zipfile.ZipFile(candidate) as jar:
            if "fabric.mod.json" not in jar.namelist():
                continue
            mod = json.loads(jar.read("fabric.mod.json"))
            if mod.get("id") == "function_compiler":
                choices.append(candidate)
    if len(choices) != 1:
        raise RuntimeError(f"Expected one remapped compiler production jar; found {choices}")
    return choices[0]


def stage_artifacts() -> dict:
    """Verify the cached official 26.3 jar and stage a pinned Fabric server."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    roots = [
        Path(os.environ.get("GRADLE_USER_HOME", Path.home() / ".gradle")),
        Path.home() / ".gradle",
        ROOT / ".gradle-user-home",
    ]
    official = locate_official_server_jar(cache_roots=roots)
    if sha256(official) != MINECRAFT_SERVER_SHA256:
        raise RuntimeError("Official Minecraft server fingerprint mismatch")

    FABRIC_BASE.mkdir(parents=True, exist_ok=True)
    shutil.copy2(official, FABRIC_BASE / "server.jar")
    installer = OUTPUT / "fabric-installer.jar"
    with urllib.request.urlopen(FABRIC_INSTALLER_URL, timeout=60) as response:
        installer.write_bytes(response.read())
    if not zipfile.is_zipfile(installer):
        raise RuntimeError("Downloaded Fabric installer is not a valid JAR")
    cmd = [
        "java", "-jar", str(installer), "server",
        "-mcversion", "26.3", "-loader", FABRIC_LOADER_VERSION,
        "-dir", str(FABRIC_BASE),
    ]
    print("Installing separate production Fabric server using installer 1.1.2", flush=True)
    done = subprocess.run(cmd, text=True, stdout=subprocess.PIPE,
                          stderr=subprocess.STDOUT, timeout=180, check=False)
    (OUTPUT / "fabric-installer.log").write_text(done.stdout, encoding="utf-8")
    if done.returncode:
        raise RuntimeError(f"Fabric installer failed ({done.returncode}): {done.stdout[-2500:]}")
    launcher = FABRIC_BASE / "fabric-server-launch.jar"
    if not launcher.is_file():
        raise RuntimeError(
            "Fabric installer did not create fabric-server-launch.jar; "
            f"files: {[x.name for x in FABRIC_BASE.iterdir()]}"
        )

    api = OUTPUT / f"fabric-api-{FABRIC_API_VERSION}.jar"
    with urllib.request.urlopen(FABRIC_API_URL, timeout=60) as response:
        api.write_bytes(response.read())
    if not zipfile.is_zipfile(api):
        raise RuntimeError("Fabric API download is not a JAR")
    with zipfile.ZipFile(api) as jar:
        mod = json.loads(jar.read("fabric.mod.json"))
        if mod.get("id") != "fabric-api":
            raise RuntimeError("Fabric API archive has an unexpected mod id")

    compiler = find_production_jar()
    artifacts = {
        "official_server_sha256": sha256(official),
        "expected_official_server_sha256": MINECRAFT_SERVER_SHA256,
        "fabric_installer_sha256": sha256(installer),
        "fabric_server_launcher_sha256": sha256(launcher),
        "fabric_api_sha256": sha256(api),
        "compiler_production_jar_sha256": sha256(compiler),
        "versions": {
            "minecraft": "26.3", "java": "25",
            "fabric_loader": FABRIC_LOADER_VERSION,
            "fabric_api": FABRIC_API_VERSION,
            "fabric_installer": FABRIC_INSTALLER_VERSION,
        },
        "official": str(official),
        "launcher": str(launcher),
        "api": str(api),
        "compiler": str(compiler),
    }
    print("Verified runtime artifacts and SHA-256 hashes: " +
          json.dumps({k: v for k, v in artifacts.items() if k.endswith("_sha256")}),
          flush=True)
    return artifacts


def make_fixture(run_dir: Path) -> None:
    data = run_dir / "world" / "datapacks" / PACK
    functions = data / "data" / PACK / "function"
    functions.mkdir(parents=True, exist_ok=True)
    (data / "pack.mcmeta").write_text(
        json.dumps({"pack": {"description": "SCHED-ATTR-002 native 26.3 function",
                             "min_format": [97, 1], "max_format": [97, 1]}}) + "\n",
        encoding="utf-8",
    )
    commands = {
        "score": f"scoreboard players add {HOLDER} {OBJECTIVE} 1",
        "condition_true": (
            f"execute if score {GATE} {OBJECTIVE} matches 1 "
            f"run scoreboard players add {HOLDER} {OBJECTIVE} 1"
        ),
        "condition_false": (
            f"execute if score {GATE} {OBJECTIVE} matches 2 "
            f"run scoreboard players add {HOLDER} {OBJECTIVE} 1"
        ),
    }
    for family, line in commands.items():
        (functions / f"{family}.mcfunction").write_text(
            (line + "\n") * COMMANDS_PER_CALL, encoding="utf-8"
        )


def setup_server_properties(run_dir: Path, port: int, rcon_port: int,
                            password: str) -> None:
    (run_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    (run_dir / "server.properties").write_text(
        "\n".join((
            "online-mode=false",
            "enable-rcon=true",
            "broadcast-rcon-to-ops=false",
            "level-name=world",
            "level-type=minecraft:flat",
            "pause-when-empty-seconds=-1",
            "view-distance=2",
            "simulation-distance=2",
            "max-tick-time=-1",
            "max-players=1",
            "sync-chunk-writes=false",
            f"server-port={port}",
            f"rcon.port={rcon_port}",
            f"rcon.password={password}",
        )) + "\n", encoding="utf-8",
    )


def server_tid(pid: int) -> int:
    """Identify Minecraft's dedicated server thread explicitly."""
    tids = []
    for task in Path(f"/proc/{pid}/task").iterdir():
        try:
            name = (task / "comm").read_text().strip()
        except OSError:
            continue
        if name == "Server thread":
            tids.append(int(task.name))
    if len(tids) != 1:
        candidates = []
        for task in Path(f"/proc/{pid}/task").iterdir():
            try:
                candidates.append((task.name, (task / "comm").read_text().strip()))
            except OSError:
                pass
        raise RuntimeError(f"Expected exactly one Minecraft Server thread in {pid}; "
                           f"found {tids}, candidates={candidates[:40]}")
    return tids[0]


def server_cpu_time_ns(pid: int, tid: int) -> tuple[int, str]:
    """Use kernel scheduler running-ns accounting; report fallback precision."""
    task = Path(f"/proc/{pid}/task/{tid}")
    sched = task / "schedstat"
    if sched.exists():
        fields = sched.read_text().split()
        if fields and int(fields[0]) > 0:
            return int(fields[0]), "linux_schedstat_ns"
    raw = (task / "stat").read_text()
    fields = raw.rsplit(")", 1)[1].split()
    # stat fields start at field 3 after the command's trailing parenthesis.
    user_ticks = int(fields[11])
    sys_ticks = int(fields[12])
    hz = os.sysconf("SC_CLK_TCK")
    return round((user_ticks + sys_ticks) * 1_000_000_000 / hz), "linux_proc_stat_ticks"


def read_score(rcon: Rcon) -> int:
    raw = rcon.command(f"scoreboard players get {HOLDER} {OBJECTIVE}")
    m = re.search(r"has (-?\d+)", raw)
    if not m:
        raise AssertionError(f"Could not read expected scoreboard score: {raw!r}")
    return int(m.group(1))


def invoke_function(rcon: Rcon, family: str) -> float:
    started = time.perf_counter_ns()
    response = rcon.command(f"function {PACK}:{family}")
    duration_ms = (time.perf_counter_ns() - started) / 1_000_000
    if not response.startswith("Running function "):
        raise AssertionError(f"Function {family} did not execute: {response!r}")
    return duration_ms


def measure_family(rcon: Rcon, pid: int, tid: int, family: str) -> dict:
    rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    for _ in range(WARMUP_CALLS):
        invoke_function(rcon, family)
    expected_warmup = (
        WARMUP_CALLS * COMMANDS_PER_CALL if family != "condition_false" else 0
    )
    if read_score(rcon) != expected_warmup:
        raise AssertionError(f"Warmup parity failed for {family}")

    before_cpu, clock_source = server_cpu_time_ns(pid, tid)
    before_wall = time.perf_counter_ns()
    latencies = []
    for _ in range(MEASURED_CALLS):
        latencies.append(invoke_function(rcon, family))
    wall_ns = time.perf_counter_ns() - before_wall
    after_cpu, clock_source_after = server_cpu_time_ns(pid, tid)
    if clock_source != clock_source_after:
        raise RuntimeError("CPU timing clock changed within a measurement window")
    expected = (
        (WARMUP_CALLS + MEASURED_CALLS) * COMMANDS_PER_CALL
        if family != "condition_false" else 0
    )
    final_score = read_score(rcon)
    if final_score != expected:
        raise AssertionError(f"Exact-work parity failed {family}: "
                             f"actual={final_score} expected={expected}")
    cpu_ns = after_cpu - before_cpu
    if cpu_ns < 0:
        raise RuntimeError("Non-monotone server-thread CPU clock")
    result = {
        "family": family,
        "commands_per_call": COMMANDS_PER_CALL,
        "warmup_calls": WARMUP_CALLS,
        "measured_calls": MEASURED_CALLS,
        "measured_source_lines": MEASURED_CALLS * COMMANDS_PER_CALL,
        "cpu_clock": clock_source,
        "server_thread_cpu_ns": cpu_ns,
        "server_thread_cpu_ns_per_source_line": round(
            cpu_ns / (MEASURED_CALLS * COMMANDS_PER_CALL), 3),
        "wall_ns": wall_ns,
        "rcon_round_trip_median_ms": round(statistics.median(latencies), 5),
        "rcon_round_trip_p95_ms": round(
            sorted(latencies)[int(.95 * (len(latencies) - 1))], 5),
        "score": final_score,
        "expected_score": expected,
        "exact_workload_parity": True,
    }
    print(
        f"CPU WINDOW family={family} "
        f"cpu_ns_per_line={result['server_thread_cpu_ns_per_source_line']} "
        f"rcon_p50_ms={result['rcon_round_trip_median_ms']} "
        f"clock={clock_source} parity=ok",
        flush=True,
    )
    return result


def jfr_diagnostic(rcon: Rcon, pid: int, mode: str, boot: int) -> dict:
    """Separate instrumentation-only flight recording, NOT a timing arm."""
    name = f"SCHED_NATIVE_{boot}"
    path = OUTPUT / f"diagnostic-{boot:02}-{mode}.jfr"
    jcmd(pid, "JFR.start", f"name={name}", "settings=profile",
         "disk=true", "dumponexit=false")
    try:
        for _ in range(JFR_DIAGNOSTIC_CALLS):
            invoke_function(rcon, "score")
    finally:
        jcmd(pid, "JFR.stop", f"name={name}", f"filename={path.resolve()}")
    if not path.is_file():
        raise RuntimeError(f"JFR diagnostic recording absent: {path}")
    return {"jfr_file": path.name, "bytes": path.stat().st_size,
            "mode": mode, "boot": boot, "diagnostic_calls": JFR_DIAGNOSTIC_CALLS,
            "note": "Standalone native server may have obfuscated class names; "
                    "raw JFR preserved for mapping, never mistaken for a CPU-timing arm."}


def run_mode(index: int, mode: str, artifacts: dict) -> dict:
    run_dir = RUN_ROOT / f"ci-native-{index:02}-{mode}"
    if run_dir.exists():
        shutil.rmtree(run_dir)
    if mode != "vanilla":
        # This staging includes the Fabric installer-created launcher,
        # official server jar and dependency libraries, but no compiler code.
        shutil.copytree(FABRIC_BASE, run_dir)
        mods_dir = run_dir / "mods"
        mods_dir.mkdir(exist_ok=True)
        shutil.copy2(Path(artifacts["api"]), mods_dir /
                     Path(artifacts["api"]).name)
        if mode == "compiler":
            shutil.copy2(Path(artifacts["compiler"]), mods_dir /
                         Path(artifacts["compiler"]).name)
    else:
        run_dir.mkdir(parents=True)
    make_fixture(run_dir)
    port, rcon_port = unused_port(), unused_port()
    password = secrets.token_hex(20)
    setup_server_properties(run_dir, port, rcon_port, password)

    server_jar = (Path(artifacts["official"]) if mode == "vanilla"
                  else run_dir / "fabric-server-launch.jar")
    cmd = ["java", *JVM_ARGS, "-jar", str(server_jar), "nogui"]
    env = dict(os.environ)
    env.update({
        "FC_WRAPPER_PROBE": "false",
        "FC_SCORE_ADD_PROTOTYPE": "false",
        "FC_FUSED_REGION_PROTOTYPE": "false",
        "FC_BYTECODE_REGION_PROTOTYPE": "false",
        "FC_SELECTIVE_MACRO_ARGUMENTS": "false",
        "FC_COMMAND_CALLBACK_METRICS": "false",
        "FC_RUNTIME_TRACE": "false",
        "FC_SCHEDULER_RESEARCH": "false",
    })
    result = {"boot": index, "mode": mode, "order": FAMILY_ORDER[index],
              "status": "running", "windows": []}
    logfile = OUTPUT / f"server-{index:02}-{mode}.log"
    print(f"BOOT {index} mode={mode} production_server={server_jar.name}",
          flush=True)
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=run_dir, env=env, stdin=subprocess.PIPE,
                                   stdout=log, stderr=subprocess.STDOUT)
        rcon = None
        try:
            rcon = wait_for_rcon(process, rcon_port, password, timeout_seconds=180)
            enabled = rcon.command("datapack list enabled")
            if PACK not in enabled:
                raise RuntimeError(f"Fixture is not enabled for {mode}: {enabled!r}")
            if mode == "compiler":
                status = rcon.command("functioncompiler status")
                if "wrapped=false" not in status:
                    raise RuntimeError(f"Compiler wrapper unexpectedly active: {status!r}")
                result["compiler_status"] = status
            else:
                status = rcon.command("functioncompiler status")
                if "FC_PROBE" in status:
                    raise RuntimeError(f"Compiler command unexpected in {mode}: {status!r}")
            rcon.command(f"scoreboard objectives add {OBJECTIVE} dummy")
            rcon.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            rcon.command(f"scoreboard players set {GATE} {OBJECTIVE} 1")
            rcon.command("gamerule sendCommandFeedback false")
            pid, tid = process.pid, server_tid(process.pid)
            cpu_0, clock = server_cpu_time_ns(pid, tid)
            start = time.perf_counter_ns()
            time.sleep(2)
            idle_wall = time.perf_counter_ns() - start
            idle_cpu = server_cpu_time_ns(pid, tid)[0] - cpu_0
            result["server_pid"] = pid
            result["server_tid"] = tid
            result["cpu_clock"] = clock
            result["idle_server_thread_cpu_ns_per_second"] = round(
                idle_cpu / (idle_wall / 1_000_000_000), 1)
            result["host_loadavg_before"] = os.getloadavg()
            result["host_cpu_count"] = os.cpu_count()
            for family in FAMILY_ORDER[index]:
                result["windows"].append(measure_family(rcon, pid, tid, family))
                result["status"] = "partial"
                REPORT.write_text(json.dumps(RUN_RECORD, indent=2) + "\n", encoding="utf-8")
            if index < 3:
                result["jfr_diagnostic"] = jfr_diagnostic(rcon, pid, mode, index)
            result["status"] = "complete"
            print(f"BOOT {index} mode={mode} complete", flush=True)
        except BaseException:
            print(f"BOOT {index} mode={mode} failed, see {logfile}", file=sys.stderr,
                  flush=True)
            raise
        finally:
            if rcon is not None:
                try:
                    rcon.command("stop")
                except (OSError, RuntimeError):
                    pass
                rcon.close()
            try:
                process.wait(timeout=40)
            except subprocess.TimeoutExpired:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
    return result


RUN_RECORD: dict = {}


def main() -> int:
    OUTPUT.mkdir(parents=True, exist_ok=True)
    artifacts = stage_artifacts()
    RUN_RECORD.update({
        "experiment": "SCHED-ATTR-002",
        "status": "started",
        "classification": "same-runner three-environment CPU screening; not a promotion gate",
        "primary_measure": "Linux /proc Server-thread running CPU ns (not RCON RTT)",
        "secondary_measure": "RCON round-trip latency, includes transport and tick scheduling",
        "server_versions": artifacts["versions"],
        "artifact_hashes": {
            k: v for k, v in artifacts.items() if k.endswith("_sha256")
        },
        "boot_sequence": MODES,
        "families": FAMILIES,
        "commands_per_function": COMMANDS_PER_CALL,
        "warmup_calls_per_window": WARMUP_CALLS,
        "measured_calls_per_window": MEASURED_CALLS,
        "modes": [],
        "important_caveats": [
            "Fabric includes Fabric API in both non-vanilla modes; compiler mode adds only the production compiler mod.",
            "All compiler optimization flags are disabled, but Mixins and registered commands remain installed.",
            "Different vanilla and Fabric launchers/classloaders are inherent to the comparison.",
            "Server thread CPU includes background game work and RCON commands; idle CPU rate is reported separately.",
            "Only two boots per mode, one CI runner, not a confirmatory repeated-host campaign.",
            "Raw JFR is collected after timed arms and not used in CPU timing.",
        ],
    })
    REPORT.write_text(json.dumps(RUN_RECORD, indent=2) + "\n", encoding="utf-8")
    try:
        for index, mode in enumerate(MODES):
            # State is checkpointed after every boot. A failed run leaves
            # partial evidence and is not incorrectly marked complete.
            RUN_RECORD["modes"].append(run_mode(index, mode, artifacts))
            REPORT.write_text(json.dumps(RUN_RECORD, indent=2) + "\n", encoding="utf-8")
        summary = defaultdict(lambda: defaultdict(list))
        for boot in RUN_RECORD["modes"]:
            for window in boot["windows"]:
                summary[window["family"]][boot["mode"]].append(
                    window["server_thread_cpu_ns_per_source_line"]
                )
        RUN_RECORD["analysis"] = {
            family: {
                mode: {
                    "cpu_ns_per_source_line_each_boot": values,
                    "median_cpu_ns_per_source_line": round(statistics.median(values), 3),
                }
                for mode, values in modes.items()
            }
            for family, modes in summary.items()
        }
        RUN_RECORD["status"] = "complete"
        REPORT.write_text(json.dumps(RUN_RECORD, indent=2) + "\n", encoding="utf-8")
        print("SCHED-ATTR-002 completed with exact workload parity; summary=" +
              json.dumps(RUN_RECORD["analysis"]), flush=True)
    except BaseException as exc:
        RUN_RECORD["status"] = "failed"
        RUN_RECORD["failure"] = repr(exc)
        REPORT.write_text(json.dumps(RUN_RECORD, indent=2) + "\n", encoding="utf-8")
        raise
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
