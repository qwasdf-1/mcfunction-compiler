#!/usr/bin/env python3
"""IR040 first speed test: same-JVM native/IR039/IR040, exact workload checks.

No profiling hooks or counters in timed JVM. Two independent JVM boots;
counterbalanced comparisons and native/native, base/base placebo blocks.
This measures running Server-thread CPU for a synthetic compound workload.
"""
from __future__ import annotations
import json
import statistics as stats
import time
from pathlib import Path
import ci_typed_ir017 as base
import ci_typed_ir040 as ir040
from ci_typed_ir008 import find_server_thread, server_cpu_ns

OUT = base.ROOT / "build/reports/COMPILER-IR-040-CPU"
PATTERNS = [
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches 1.. if score #g fc_ir <= #y fc_ir if score #y fc_ir >= #g fc_ir run scoreboard players add #x fc_ir 1",
    "execute if score #g fc_ir matches 5..8 if score #g fc_ir matches 6..9 unless score #g fc_ir matches 10.. if score #y fc_ir > #g fc_ir run scoreboard players add #x fc_ir 1",
    "execute if score #g fc_ir matches 5.. if score #g fc_ir matches ..3 if score #g fc_ir matches 7 if score #y fc_ir matches 9 run scoreboard players add #x fc_ir 100",
    "execute unless score #g fc_ir matches 0..2 if score #g fc_ir matches 6.. if score #y fc_ir > #g fc_ir if score #g fc_ir < #y fc_ir run scoreboard players add #x fc_ir 1",
]
COMMANDS = PATTERNS * 16
CALLS = 64
BATCHES = 8
WARMUP = 8
BOOTS = 2
ARMS = ("native","base","flow")
COMPARISONS = (("native","flow"),("base","flow"),("native","native"),("base","base"))
MIN_REDUCTION = .05
AA_LIMIT = .05
original_fixture = base.fixture
DIAGNOSTIC_PREFLIGHT = False

def fixture(work):
    original_fixture(work)
    folder = work/"world/datapacks"/base.PACK/"data/fc_native/function"
    folder.mkdir(parents=True,exist_ok=True)
    (folder/"ir017_ir040_perf.mcfunction").write_text("\n".join(COMMANDS)+"\n")

def options(mode):
    flags=ir040.options(mode)
    flags.update({"FC_TYPED_IR040_BENCHMARK":"true",
                  "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC_PREFLIGHT).lower(),
                  "FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"false",
                  "FC_TYPED_IR_ARITHMETIC":"false"})
    return flags

def batch(client,arm):
    reply=client.command(f"fc_ir040_batch {arm} {CALLS}")
    if f"IR040_BATCH {arm} {CALLS}" not in reply:
        raise AssertionError(f"batch rejected: {reply!r}")

def prepare(client):
    client.command("gamerule minecraft:max_command_sequence_length 1000000")
    client.command("scoreboard players set #g fc_ir 7")
    client.command("scoreboard players set #y fc_ir 9")
    client.command("scoreboard players set #x fc_ir 0")

def validate(client,batches):
    observed={k:base.nullable_score(client,"#"+k,"fc_ir") for k in ("x","g","y")}
    expected={"x":48*CALLS*batches,"g":7,"y":9}
    if observed!=expected: raise AssertionError(f"exact work mismatch: {observed} != {expected}")
    return observed

def preflight():
    global DIAGNOSTIC_PREFLIGHT
    DIAGNOSTIC_PREFLIGHT=True
    process,client,log=base.start("bytecode")
    try:
        layouts={name:base.inspect(client,name) for name in
                 ("ir017_ir040_perf","ir017_ir040_perf_base")}
        if any(v["typed_lines"]!=64 for v in layouts.values()):
            raise AssertionError(f"benchmark functions not fully compiled: {layouts}")
        native=client.command("functioncompiler ir016 fc_native:ir017_ir040_perf")
        if "no ledger entry" not in native:
            raise AssertionError(f"native twin unexpectedly compiled: {native}")
        from ci_typed_ir038 import stat
        proof={}
        for arm in ARMS:
            prepare(client)
            before=client.command("functioncompiler ir008")
            batch(client,arm)
            state=validate(client,1)
            after=client.command("functioncompiler ir008")
            delta={key:stat(after,key)-stat(before,key) for key in
                   ("ir040_proofs","ir040_operand_reads_reused","executed_regions")}
            if arm=="native" and any(delta.values()):
                raise AssertionError(f"native twin executed compiled path: {delta}")
            if arm=="base" and (delta["ir040_proofs"] or delta["ir040_operand_reads_reused"]
                                or delta["executed_regions"]<=0):
                raise AssertionError(f"IR039 twin did not isolate dataflow: {delta}")
            if arm=="flow" and any(v<=0 for v in delta.values()):
                raise AssertionError(f"IR040 twin not exercised: {delta}")
            proof[arm]={"state":state,"counter_deltas":delta}
        result={"layouts":layouts,"native_layout":native,"arms":proof}
        (OUT/"diagnostic-preflight.json").write_text(json.dumps(result,indent=2)+"\n")
        return result
    finally:
        base.stop(process,client,log)
        DIAGNOSTIC_PREFLIGHT=False
        p=OUT/"bytecode.server.log"
        if p.exists(): p.rename(OUT/"diagnostic-preflight.server.log")

def run_boot(boot):
    process,client,log=base.start("bytecode")
    report={"boot":boot,"blocks":[],"status":"started"}
    try:
        thread=find_server_thread(process.pid)
        for arm in (ARMS if boot==0 else ARMS[::-1]):
            prepare(client)
            for _ in range(WARMUP): batch(client,arm)
            validate(client,WARMUP)
        def window(arm):
            prepare(client)
            cpu_start=server_cpu_ns(thread)
            wall_start=time.monotonic_ns()
            for _ in range(BATCHES): batch(client,arm)
            wall=time.monotonic_ns()-wall_start
            cpu=server_cpu_ns(thread)-cpu_start
            if cpu<=0: raise AssertionError("invalid Server-thread CPU")
            return {"arm":arm,"cpu_ns":cpu,"wall_ns":wall,"lines":64*CALLS*BATCHES,
                    "state":validate(client,BATCHES)}
        # Four comparison types; each has both ABBA and BAAB per boot.
        for order in (("ABBA","BAAB") if boot==0 else ("BAAB","ABBA")):
            pairs=COMPARISONS if order=="ABBA" else COMPARISONS[::-1]
            for a,b in pairs:
                samples=[window(a if label=="A" else b) for label in order]
                av=stats.mean(s["cpu_ns"] for s,label in zip(samples,order) if label=="A")
                bv=stats.mean(s["cpu_ns"] for s,label in zip(samples,order) if label=="B")
                block={"a":a,"b":b,"order":order,"samples":samples,"reduction":1-bv/av}
                report["blocks"].append(block)
                print("IR040_CPU_BLOCK "+json.dumps({"boot":boot,"a":a,"b":b,"order":order,
                    "cpu_ns_per_line_a":av/(64*CALLS*BATCHES),
                    "cpu_ns_per_line_b":bv/(64*CALLS*BATCHES),"reduction":block["reduction"]}),flush=True)
                (OUT/f"boot-{boot}.json").write_text(json.dumps(report,indent=2)+"\n")
        report["status"]="accepted"
        return report
    finally:
        base.stop(process,client,log)
        (OUT/f"boot-{boot}.json").write_text(json.dumps(report,indent=2)+"\n")
        # base.start uses the same mode filename on both boots.
        path=OUT/"bytecode.server.log"
        if path.exists(): path.rename(OUT/f"boot-{boot}.server.log")

def analyze(boots):
    all_blocks=[b for boot in boots for b in boot["blocks"]]
    aa=max(abs(b["reduction"]) for b in all_blocks if b["a"]==b["b"])
    findings={}
    for a,b in COMPARISONS[:2]:
        records=[x for x in all_blocks if (x["a"],x["b"])==(a,b)]
        medians=[stats.median(x["reduction"] for x in boot["blocks"] if (x["a"],x["b"])==(a,b))
                 for boot in boots]
        reduction=stats.median(x["reduction"] for x in records)
        findings[f"{a}_vs_{b}"]={"median_cpu_reduction":reduction,"boot_medians":medians,
             "all_blocks": [x["reduction"] for x in records],
             "pilot_gate_pass":aa<=AA_LIMIT and min(medians)>=max(MIN_REDUCTION,2*aa)
                               and all(x["reduction"]>0 for x in records)}
    return {"status":"synthetic_pilot_complete","aa_max_absolute":aa,"aa_gate_pass":aa<=AA_LIMIT,
            "findings":findings,"scope":"synthetic native server-thread CPU only",
            "general_datapack_speedup":False,"production_promotion":False}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS={"ir017_ir040_perf":COMMANDS,"ir017_ir040_perf_base":COMMANDS}
    base.fixture=fixture
    base.options=options
    report={"status":"started","boots":[]}
    try:
        report["preflight"]=preflight()
        for boot in range(BOOTS):
            report["boots"].append(run_boot(boot))
        report["summary"]=analyze(report["boots"])
        report["status"]="complete"
        print("IR040_CPU_SUMMARY "+json.dumps(report["summary"]),flush=True)
    except BaseException as e:
        report.update(status="invalid",error=repr(e))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(report,indent=2)+"\n")

if __name__=="__main__":
    main()
