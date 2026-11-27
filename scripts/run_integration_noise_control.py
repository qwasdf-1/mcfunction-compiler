#!/usr/bin/env python3
"""Launch exactly one unchanged qualification protocol with controlled placement."""
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import traceback

import ci_typed_ir017 as base
from ci_typed_ir008 import find_server_thread
import integration_cpu_placement as placement

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build/reports/INTEGRATION-NOISE-CONTROL"
SCRIPTS={"047_cpu":"ci_typed_ir047_cpu.py",
         "default_off":"ci_integration_001_off.py",
         "absolute_pure":"ci_integration_001_absolute.py",
         "absolute_mixed":"ci_integration_001_absolute.py"}
def command(args,cwd=ROOT):
    p=subprocess.run(args,cwd=cwd,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
    return {"returncode":p.returncode,"output":p.stdout}
def fingerprint(root):
    files=sorted((root/"build/libs").glob("*.jar"))
    result={"commit":command(["git","rev-parse","HEAD"],root),
            "jars":{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    for directory in ("build/classes/java/main","build/resources/main"):
        path=root/directory
        h=hashlib.sha256()
        for p in sorted(x for x in path.rglob("*") if x.is_file()):
            h.update(str(p.relative_to(path)).encode()+b"\0")
            h.update(hashlib.sha256(p.read_bytes()).digest())
        result[directory]=h.hexdigest()
    return result
def save(report):
    OUT.mkdir(parents=True,exist_ok=True)
    (OUT/"host.json").write_text(json.dumps(report,indent=2)+"\n")
def main():
    suite=sys.argv[1]
    if suite not in SCRIPTS:raise ValueError(suite)
    args=sys.argv[2:]
    if (suite=="047_cpu" and args) or (suite!="047_cpu" and len(args)!=1):
        raise ValueError("expected pinned twin checkout for cross-build comparisons")
    report={"suite":suite,"status":"started","runner_environment":os.environ.get("RUNNER_ENVIRONMENT"),
            "java":command(["java","-version"]),"uname":command(["uname","-a"]),
            "lscpu":command(["lscpu","--json"]),"cpuinfo":placement.read("/proc/cpuinfo"),
            "cgroup_cpu_max":placement.read("/sys/fs/cgroup/cpu.max"),
            "cgroup_cpuset_effective":placement.read("/sys/fs/cgroup/cpuset.cpus.effective"),
            "candidate":fingerprint(ROOT),"baseline":fingerprint(Path(args[0])) if args else None,
            "boots":[],"runtime_instrumentation":False,
            "frequency_note":"endpoint sysfs samples only; null means unavailable; no cycle normalization"}
    try:
        report["placement"]=placement.configure()
        base.EXTRA_JVM_ARGS=("-XX:ActiveProcessorCount=4",)
        report["jvm_args"]=["-Xms512M","-Xmx2G",*base.EXTRA_JVM_ARGS]
        original=base.start
        def start(mode):
            process,client,log=original(mode)
            try:
                info=placement.bind_server(find_server_thread(process.pid))
                report["boots"].append(info|{"mode":mode,"root":str(base.ROOT)})
                save(report)
                return process,client,log
            except BaseException:
                base.stop(process,client,log)
                raise
        base.start=start
        save(report)
        sys.argv=[str(ROOT/"scripts"/SCRIPTS[suite]),*args]
        runpy.run_path(sys.argv[0],run_name="__main__")
        report["status"]="protocol_completed"
    except BaseException as exc:
        report.update(status="invalid",error=repr(exc),traceback=traceback.format_exc())
        raise
    finally:save(report)
if __name__=="__main__":main()
