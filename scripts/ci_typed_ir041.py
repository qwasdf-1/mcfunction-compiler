#!/usr/bin/env python3
"""IR041 preregistered steady-state qualification, paired CPU, mixed work.

Do not time treatments before warmup + placebo gates pass. Retain every sample.
No change to IR040's historic experiment or production execution flags.
"""
from __future__ import annotations

import json
import re
import statistics as stats
import time
from pathlib import Path
import ci_typed_ir017 as base
import ci_typed_ir040_cpu as previous
from ci_typed_ir038 import stat
from ci_typed_ir008 import find_server_thread, server_cpu_ns
from benchmark_noise_telemetry import snapshot_jvm_environment, delta_environment

OUT = base.ROOT / "build/reports/COMPILER-IR-041"
ARMS = ("native", "base", "flow")
WORKLOADS = ("compound", "mixed")
CALLS = 128
BATCHES = 64
MIN_ROUNDS = 6
MAX_ROUNDS = 16
STABLE_WINDOWS = 4
SPREAD_LIMIT = .05
AA_LIMIT = .05
MIN_REDUCTION = .05
MIN_CPU_NS = 20_000_000
BOOTS = 2
DIAGNOSTIC = False
ORIGINAL_FIXTURE = base.fixture

# Vary the live value, guard outcomes, arithmetic and opaque boundaries.
# The shared child is intentionally native in every arm; the top-level source
# is byte-identical across twins. A full call changes x by 92.
MIXED = []
for i in range(1, 9):
    MIXED.extend([
        f"scoreboard players set #g fc_ir {i}",
        "execute if score #g fc_ir matches 1.. if score #g fc_ir < #y fc_ir run scoreboard players add #x fc_ir 1",
        "execute if score #g fc_ir matches 5.. if score #g fc_ir matches 1.. run scoreboard players add #x fc_ir 2",
        "execute unless score #g fc_ir matches ..4 if score #g fc_ir matches ..7 run scoreboard players add #x fc_ir 4",
        "scoreboard players operation #result fc_ir = #g fc_ir",
        "scoreboard players operation #result fc_ir *= #y fc_ir",
        ("execute store result score #observed fc_ir run scoreboard players get #result fc_ir"
         if i % 2 else "function fc_native:ir041_mixed_copy"),
        "execute if score #observed fc_ir matches 1.. run scoreboard players add #x fc_ir 8",
    ])
CHILD = ["scoreboard players operation #observed fc_ir = #result fc_ir"]
COMMANDS = {"compound": previous.COMMANDS, "mixed": MIXED}
PATHS = {"compound": "ir017_ir040_perf", "mixed": "ir017_ir041_mixed"}
LINES = {k: len(v) for k,v in COMMANDS.items()}
# Count the top-level visits and actual nested native one-line calls separately.
NESTED = {"compound": 0, "mixed": 4}

def options(mode):
    flags = previous.options(mode)
    flags.update({
        "FC_TYPED_IR041_BENCHMARK":"true",
        "FC_IR041_COMPILE_TIMING":str(DIAGNOSTIC).lower(),
        "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC).lower(),
        "FC_TYPED_IR_ARITHMETIC":"false",
        "FC_TYPED_IR_REENTRANT_TEST_OBSERVER":"false",
        "FC_BENCH_COMPILE_TIMING":"false",
        "FC_COMPILER_EXEC_CENSUS":"false",
        "FC_FUNCTION_TIMING":"false",
    })
    return flags

def fixture(work):
    ORIGINAL_FIXTURE(work)
    folder=work/"world/datapacks"/base.PACK/"data/fc_native/function"
    folder.mkdir(parents=True,exist_ok=True)
    for kind,path in PATHS.items():
        (folder/(path+".mcfunction")).write_text("\n".join(COMMANDS[kind])+"\n")
    (folder/"ir041_mixed_copy.mcfunction").write_text("\n".join(CHILD)+"\n")

def prepare(client,workload):
    for key,value in (("g",7),("y",9),("x",0),("result",0),("observed",0)):
        client.command(f"scoreboard players set #{key} fc_ir {value}")
    client.command("gamerule minecraft:max_command_sequence_length 1000000")

def batch(client,workload,arm):
    token=arm if workload=="compound" else "mixed_"+arm
    reply=client.command(f"fc_ir040_batch {token} {CALLS}")
    if f"IR040_BATCH {token} {CALLS}" not in reply:
        raise AssertionError(f"batch rejected: {reply!r}")

def validate(client,workload,batches):
    keys=("x","g","y","result","observed")
    actual={k:base.nullable_score(client,"#"+k,"fc_ir") for k in keys}
    expected=({"x":48*CALLS*batches,"g":7,"y":9,"result":0,"observed":0}
              if workload=="compound" else
              {"x":92*CALLS*batches,"g":8,"y":9,"result":72,"observed":72})
    if actual!=expected: raise AssertionError(f"{workload}: exact work {actual} != {expected}")
    return actual

def setup(client):
    # Freeze simulation, NOT the command queue. All arms still run the same
    # Minecraft function scheduling, RCON and command feedback path.
    reply=client.command("tick freeze")
    if "frozen" not in reply.lower():
        raise AssertionError(f"Could not confirm tick freeze: {reply!r}")
    return reply

def stop(process,client,log,name):
    base.stop(process,client,log)
    p=OUT/"bytecode.server.log"
    if p.exists(): p.rename(OUT/(name+".server.log"))

def preflight():
    global DIAGNOSTIC
    DIAGNOSTIC=True
    process,client,log=base.start("bytecode")
    report={}
    try:
        report["freeze"]=setup(client)
        for workload,path in PATHS.items():
            native=client.command("functioncompiler ir016 fc_native:"+path)
            if "no ledger entry" not in native: raise AssertionError("native compiled")
            layouts={arm:base.inspect(client,path+("_base" if arm=="base" else ""))
                     for arm in ("base","flow")}
            # Seven post-barrier guards join the following group's six
            # typed commands. Only the final guard is an isolated singleton.
            expected=64 if workload=="compound" else 55
            if any(x["typed_lines"]!=expected for x in layouts.values()):
                raise AssertionError(f"{workload}: unexpected coverage {layouts}")
            if workload=="mixed" and any(x["opaque_barriers"]<8 for x in layouts.values()):
                raise AssertionError("mixed workload lost opaque boundary")
            evidence={}
            for arm in ARMS:
                prepare(client,workload)
                before=client.command("functioncompiler ir008")
                batch(client,workload,arm)
                state=validate(client,workload,1)
                after=client.command("functioncompiler ir008")
                delta={k:stat(after,k)-stat(before,k) for k in
                       ("ir040_proofs","ir040_operand_reads_reused","executed_regions")}
                if arm=="native" and any(delta.values()): raise AssertionError("native path drift")
                if arm=="base" and (delta["ir040_proofs"] or delta["ir040_operand_reads_reused"]
                                     or not delta["executed_regions"]):
                    raise AssertionError("base path drift")
                if arm=="flow" and not (delta["ir040_proofs"]>0 and delta["executed_regions"]>0):
                    raise AssertionError("flow path not exercised")
                evidence[arm]={"delta":delta,"state":state}
            report[workload]={"layouts":layouts,"native_layout":native,"arms":evidence}
    finally:
        stop(process,client,log,"diagnostic")
        DIAGNOSTIC=False
    log=(OUT/"diagnostic.server.log").read_text(errors="replace")
    pattern=r"IR041_COMPILE function=(\S+) source_lines=(\d+) wall_ns=(\d+) thread_cpu_ns=(-?\d+)"
    compile_rows=[{"function":m[0],"source_lines":int(m[1]),"wall_ns":int(m[2]),"thread_cpu_ns":int(m[3])}
                  for m in re.findall(pattern,log)]
    expected={"fc_ir:"+p+s for p in PATHS.values() for s in ("","_base")}
    if {row["function"] for row in compile_rows}!=expected or any(r["wall_ns"]<=0 for r in compile_rows):
        raise AssertionError(f"compile-only timing missing: {compile_rows}")
    report["compile_only"]=compile_rows
    (OUT/"diagnostic-preflight.json").write_text(json.dumps(report,indent=2)+"\n")
    print("IR041_PREFLIGHT "+json.dumps(report),flush=True)
    return report

def cost(sample): return sample["cpu_ns"]/sample["top_level_lines"]

def spread(samples):
    values=[cost(x) for x in samples]
    return (max(values)-min(values))/stats.median(values)

def qualify(history):
    # A predeclared consecutive tail, never selected using treatment results.
    if any(len(history[a])<MIN_ROUNDS for a in ARMS): return False
    return all(spread(history[a][-STABLE_WINDOWS:])<=SPREAD_LIMIT
               and min(x["cpu_ns"] for x in history[a][-STABLE_WINDOWS:])>=MIN_CPU_NS
               for a in ARMS)

def paired(a,b,order,window):
    samples=[window(a if label=="A" else b) for label in order]
    av=stats.mean(cost(s) for s,label in zip(samples,order) if label=="A")
    bv=stats.mean(cost(s) for s,label in zip(samples,order) if label=="B")
    return {"a":a,"b":b,"order":order,"samples":samples,
            "a_ns_per_line":av,"b_ns_per_line":bv,"reduction":1-bv/av}

def aa_pass(blocks):
    return bool(blocks) and all(abs(b["reduction"])<=AA_LIMIT
                              and min(s["cpu_ns"] for s in b["samples"])>=MIN_CPU_NS
                              for b in blocks)

def analyze_workload(workload,boots):
    entries=[b["workloads"][workload] for b in boots]
    qualified=len(entries)==BOOTS and all(e["status"]=="complete" for e in entries)
    blocks=[x for e in entries for x in e["blocks"]]
    aa=[abs(x["reduction"]) for x in blocks if x["a"]==x["b"]]
    max_aa=max(aa,default=None)
    measurements={}
    for a in ("native","base"):
        arm=[x for x in blocks if x["a"]==a and x["b"]=="flow"]
        per_boot=[[x["reduction"] for x in e["blocks"] if x["a"]==a and x["b"]=="flow"]
                  for e in entries]
        medians=[stats.median(x) for x in per_boot if x]
        passed=(qualified and max_aa is not None and max_aa<=AA_LIMIT
                and len(arm)==2*BOOTS and all(x["reduction"]>0 for x in arm)
                and len(medians)==BOOTS and min(medians)>=max(MIN_REDUCTION,2*max_aa)
                and all(s["cpu_ns"]>=MIN_CPU_NS for x in arm for s in x["samples"]))
        measurements[a+"_vs_flow"]={"paired_reductions":[x["reduction"] for x in arm],
              "median_reduction":stats.median(x["reduction"] for x in arm) if arm else None,
              "boot_medians":medians,"pilot_gate_pass":bool(passed)}
    return {"qualified_both_boots":qualified,"max_absolute_aa":max_aa,
            "boot_statuses":[e["status"] for e in entries],"findings":measurements}

def run_boot(boot):
    process,client,log=base.start("bytecode")
    report={"boot":boot,"workloads":{},"status":"started"}
    def save(): (OUT/f"boot-{boot}.json").write_text(json.dumps(report,indent=2)+"\n")
    try:
        thread=find_server_thread(process.pid)
        report["freeze"]=setup(client)
        for workload in (WORKLOADS if boot==0 else WORKLOADS[::-1]):
            entry={"status":"warming","warmup":{a:[] for a in ARMS},"blocks":[]}
            report["workloads"][workload]=entry
            def window(arm):
                prepare(client,workload)
                environment0=snapshot_jvm_environment(thread[0])
                cpu0=server_cpu_ns(thread)
                wall0=time.monotonic_ns()
                for _ in range(BATCHES): batch(client,workload,arm)
                wall=time.monotonic_ns()-wall0
                cpu=server_cpu_ns(thread)-cpu0
                environment1=snapshot_jvm_environment(thread[0])
                if cpu<=0: raise AssertionError("nonpositive CPU clock")
                result={"arm":arm,"cpu_ns":cpu,"wall_ns":wall,
                        "top_level_lines":LINES[workload]*CALLS*BATCHES,
                        "nested_lines":NESTED[workload]*CALLS*BATCHES,
                        "state":validate(client,workload,BATCHES),
                        "environment":delta_environment(environment0,environment1)}
                return result
            # Counterbalance warmup order and workload order independently of results.
            for round_index in range(MAX_ROUNDS):
                offset=(round_index+boot)%len(ARMS)
                order=ARMS[offset:]+ARMS[:offset]
                for arm in order: entry["warmup"][arm].append(window(arm))
                metrics={a:spread(entry["warmup"][a][-STABLE_WINDOWS:])
                         for a in ARMS}
                print("IR041_WARMUP "+json.dumps({"boot":boot,"workload":workload,
                    "round":round_index+1,"spreads":metrics,
                    "cpu_ns_per_line":{a:cost(entry["warmup"][a][-1]) for a in ARMS}}),flush=True)
                save()
                if qualify(entry["warmup"]): break
            if not qualify(entry["warmup"]):
                entry["status"]="warmup_unqualified"
                save()
                continue
            entry["status"]="qualifying_aa"
            def record(a,b,order,phase):
                block=paired(a,b,order,window)
                block["phase"]=phase
                entry["blocks"].append(block)
                save()
                print("IR041_BLOCK "+json.dumps({k:v for k,v in block.items() if k!="samples"}|
                    {"boot":boot,"workload":workload}),flush=True)
                return block
            # Independent identical-arm controls BEFORE any treatment.
            gate=[record(a,a,"ABBA" if (i+boot)%2==0 else "BAAB","qualification")
                  for i,a in enumerate(ARMS)]
            if not aa_pass(gate):
                entry["status"]="placebo_unqualified"
                save()
                continue
            # Two cycles with all A/A controls bracketing/interleaving treatment.
            for order in (("ABBA","BAAB") if boot==0 else ("BAAB","ABBA")):
                pairs=(("native","native"),("native","flow"),("flow","flow"),
                       ("base","flow"),("base","base"))
                for a,b in (pairs if order=="ABBA" else pairs[::-1]):
                    record(a,b,order,"measurement")
            controls=[b for b in entry["blocks"] if b["a"]==b["b"]]
            entry["status"]="complete" if aa_pass(controls) else "measurement_placebo_failed"
            save()
        report["status"]="complete"
        return report
    finally:
        stop(process,client,log,f"boot-{boot}")
        save()

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    base.OUT=OUT
    base.FUNCTIONS={p+s:COMMANDS[k] for k,p in PATHS.items() for s in ("","_base")}
    base.fixture=fixture
    base.options=options
    result={"status":"started","boots":[],"production_promotion":False}
    try:
        result["preflight"]=preflight()
        for boot in range(BOOTS):
            result["boots"].append(run_boot(boot))
        result["summary"]={w:analyze_workload(w,result["boots"]) for w in WORKLOADS}
        result["status"]="complete"
        print("IR041_SUMMARY "+json.dumps(result["summary"]),flush=True)
    except BaseException as error:
        result.update(status="invalid",error=repr(error))
        raise
    finally:
        (OUT/"results.json").write_text(json.dumps(result,indent=2)+"\n")

if __name__=="__main__":
    main()
