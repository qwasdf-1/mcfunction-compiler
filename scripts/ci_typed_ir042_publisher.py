#!/usr/bin/env python3
"""IR042 bounded original Blastback census and native-vs-selected-typed CPU.

All source bytes pinned. Separate diagnostic and timing JVMs. No same-JVM
native switch: the typed adapter may rewrite the original parsed callbacks.
"""
from __future__ import annotations
from collections import Counter, defaultdict
import hashlib, json, re, statistics as stats, time
from pathlib import Path
import ci_typed_ir026_blastback as base
import ci_typed_ir027_native_oracle as oracle
from ci_typed_ir027_stable_parity import checkpoint_accepted, normalized
from ci_typed_ir019_native import parse_log
from ci_typed_ir019_blastback import ALLOWLIST, CALLEES
from ci_typed_ir041_source import shape
from ci_typed_ir015_coverage import barrier
from run_specialization_inventory import Pack
from ci_typed_ir013 import stop,stat
from ci_typed_ir008 import find_server_thread
from ci_server_event_cpu import read_thread_schedstat,cgroup_throttle_count,event_cpu_delta
from benchmark_noise_telemetry import snapshot_jvm_environment,delta_environment
from run_blastback_profile import score,region_matches_template

OUT=base.ROOT/"build/reports/COMPILER-IR-042-PUBLISHER"
AA_LIMIT=.05
MIN_REDUCTION=.05
TICKS=600
CANDIDATES=("erb_generated:restore/reset","erb_generated:restore/wrap",
            "erb:restore/job_tick","erb:source/projectile_probe_step","erb:watch/player_state")
NATIVE_TARGETS=()
CALLEE_TARGETS=()
SELECTED=None
MODE="native"
DIAGNOSTIC=False
CENSUS=False

def regions(lines):
    flags=[shape(s) is not None for s in lines]
    indices=set()
    i=0
    while i<len(flags):
        if not flags[i]:
            i+=1
            continue
        end=i
        while end<len(flags) and flags[end]:end+=1
        for j in range(i,end,64):
            if min(end-j,64)>=2:indices.update(range(j,min(j+64,end)))
        i=end
    return indices

def allowlists(pack):
    targets=[]
    count=0
    # Predeclared candidates first, inherited capture/dispatch targets next;
    # macros are not stable source-index observations and are call-count only.
    for fid in dict.fromkeys((*CANDIDATES,*ALLOWLIST)):
        lines=pack.functions.get(fid)
        if not lines or any(s.startswith("$") or "$(" in s for s in lines):
            continue
        if count+len(lines)<=900:
            targets.append(fid)
            count+=len(lines)
    calls=tuple(dict.fromkeys((*CANDIDATES,*targets,*CALLEES)))
    if len(calls)>96 or not targets:raise AssertionError("invalid census scope")
    return tuple(targets),calls

def options(_):
    enabled=MODE=="compiled"
    return {**base.DISABLED_FLAGS,
        "FC_WRAPPER_PROBE":str(enabled or CENSUS).lower(),
        "FC_TYPED_IR_MODE":"bytecode" if enabled else "",
        "FC_TYPED_IR_NAMESPACE":SELECTED.split(":")[0] if enabled else "",
        "FC_TYPED_IR_FUNCTION_FILTER":SELECTED if enabled else "",
        "FC_TYPED_IR_EXTENDED_SCORE":"true",
        "FC_TYPED_IR_RANGE_GUARDS":"true",
        "FC_TYPED_IR_SELF_HOLDER":"true",
        "FC_TYPED_IR_COMPOUND_SCORE":"true",
        "FC_TYPED_IR_DATAFLOW":"true",
        "FC_TYPED_IR_ARITHMETIC":"true",
        "FC_TYPED_IR_NATIVE_FORK_PLAN":"false",
        "FC_TYPED_IR_COMPILED_FORK":"false",
        "FC_TYPED_IR_REENTRANT_SAFE":"true",
        "FC_TYPED_IR_DIAGNOSTICS":str(DIAGNOSTIC).lower(),
        "FC_COMPILER_EXEC_CENSUS":str(CENSUS).lower(),
        "FC_IR042_BLASTBACK_CENSUS":str(CENSUS).lower(),
        "FC_COMPILER_EXEC_CENSUS_NAMESPACE":"erb" if CENSUS else "",
        "FC_COMPILER_EXEC_CENSUS_FUNCTIONS":",".join(NATIVE_TARGETS) if CENSUS else "",
        "FC_COMPILER_EXEC_CENSUS_CALLEES":",".join(CALLEE_TARGETS) if CENSUS else "",
        "FC_IR041_COMPILE_TIMING":str(DIAGNOSTIC).lower(),
        "FC_IR042_COMPILE_TARGET":SELECTED if DIAGNOSTIC else "",
        "FC_BENCH_COMPILE_TIMING":"false",
        "FC_FUNCTION_TIMING":"false",
        "FC_SCORE_ADD_METRICS":"false",
        "FC_SCORE_ADD_TIMING":"false",
        "FC_RUNTIME_TRACE":"false",
        "FC_COMMAND_CALLBACK_METRICS":"false",
        "FC_SCHED_ARCH_COUNTERS":"false",
        "FC_TYPED_IR_COST_POLICY":"",
    }

def event(client,thread=None,label="event",census=False):
    oracle.configure_stable_original_scene(client)
    # All samples must start from the verified full stone scene and no active job.
    prior=oracle.observe(client,label+"-before",include_slices=False)
    if not checkpoint_accepted(prior):
        raise AssertionError("event starting state not clean: "+repr(prior))
    if census and "FC_EXEC started" not in client.command("functioncompiler exec-census-start"):
        raise AssertionError("census start refused")
    env0=snapshot_jvm_environment(thread[0]) if thread else None
    throttle0=cgroup_throttle_count() if thread else None
    tick0=score(client,"#tick_id","erb.cfg")
    before=read_thread_schedstat(*thread) if thread else None
    wall0=time.monotonic_ns()
    spawn,actor=base.verify_started_actor(client)
    deadline=time.monotonic()+60
    peak=0
    polls=0
    while peak<1000:
        peak=max(peak,oracle.count_native(client,"#fc042_count","@e[type=minecraft:marker,tag=erb.block]"))
        polls+=1
        if time.monotonic()>deadline:raise AssertionError("capture witness <1000")
        if peak<1000:time.sleep(.2)
    end=oracle.until(client,tick0+TICKS,time.monotonic()+105)
    after=read_thread_schedstat(*thread) if thread else None
    wall=time.monotonic_ns()-wall0
    env1=snapshot_jvm_environment(thread[0]) if thread else None
    throttle1=cgroup_throttle_count() if thread else None
    if census:
        reply=client.command("functioncompiler exec-census-stop")
        if "FC_EXEC ended" not in reply or "overflow=0" not in reply:
            raise AssertionError("census incomplete: "+reply)
    state=oracle.observe(client,label+"-after",include_slices=True)
    if not checkpoint_accepted(state) or oracle.count_native(client,"#fc042_count",
            "@e[type=minecraft:tnt,tag=fc_blastback_probe]")!=0:
        raise AssertionError("original event did not complete and restore: "+repr(state))
    result={"ticks":end-tick0,"max_sampled_capture":peak,"capture_polls":polls,
            "state":normalized(state),"wall_ns":wall}
    if thread:
        cpu=event_cpu_delta(before,after,throttle0,throttle1)
        result.update(cpu=cpu,cpu_ns_per_tick=cpu["server_thread_cpu_running_ns"]/(end-tick0),
                      environment=delta_environment(env0,env1))
    return result

def launch(label,mode,diagnostic=False,census=False):
    global MODE,DIAGNOSTIC,CENSUS
    MODE,DIAGNOSTIC,CENSUS=mode,diagnostic,census
    base.OUT=OUT
    base.options=options
    return base.launch(label)

def save(name,data):
    (OUT/(name+".json")).write_text(json.dumps(data,indent=2)+"\n")

def opportunity(line):
    if shape(line):return "isolated_typed_candidate"
    if re.search(r"\brun (?:return run )?function ",line) or line.startswith("function "):
        return "function_dispatch_or_macro" if " with " in line or "$(" in line else "function_dispatch"
    if re.search(r"\b(?:as|at|positioned as) @",line):return "entity_context_or_selector"
    if line.startswith("data ") or " run data " in line or "store " in line:return "data_or_store"
    return barrier(line)

def summarize_rows(rows,calls,pack):
    counts=defaultdict(Counter)
    blockers=Counter()
    selected_indices={}
    seen=set()
    for row in rows:
        fid=row["function"]
        index=int(row["index"])
        if fid not in NATIVE_TARGETS or (fid,index) in seen:
            raise AssertionError("unexpected or duplicate source site")
        seen.add((fid,index))
        lines=pack.functions[fid]
        if index>=len(lines) or row["input"]!=lines[index][:240]:
            raise AssertionError(f"source-index mismatch {fid}:{index}: {row['input']!r}")
        n=int(row["entries"])
        c=int(row["callbacks"])
        r=selected_indices.setdefault(fid,regions(lines))
        counts[fid]["entries"]+=n
        counts[fid]["ordinary_callbacks"]+=c
        if index in r: counts[fid]["candidate_region_entries"]+=n
        else: blockers[opportunity(lines[index])]+=n
    for fid in NATIVE_TARGETS:
        if sum(f==fid for f,_ in seen)!=len(pack.functions[fid]):
            raise AssertionError("missing registered source sites: "+fid)
    result=[{"function":fid,"native_call_tasks":calls.get(fid,0),
             **dict(counts[fid])} for fid in NATIVE_TARGETS]
    result.sort(key=lambda x:(-x.get("candidate_region_entries",0),x["function"]))
    return {"functions":result,"all_allowlisted_calls":calls,"unsupported_entry_rank":blockers.most_common(),
            "observed_scope_entries":sum(x["entries"] for x in result),
            "candidate_region_entries":sum(x.get("candidate_region_entries",0) for x in result),
            "static_region_prediction_only":True}

def native_census(pack):
    proc,client,log=launch("census","native",census=True)
    r={"status":"started","target_functions":NATIVE_TARGETS,"callee_functions":CALLEE_TARGETS}
    try:
        r["event"]=event(client,label="census",census=True)
        r["status"]="observed"
    finally:
        stop(proc,client,log)
        save("census",r)
    rows,calls=parse_log(OUT/"census.server.log")
    r["rows"]=rows
    r["summary"]=summarize_rows(rows,calls,pack)
    save("census",r)
    print("IR042_CENSUS "+json.dumps(r["summary"]),flush=True)
    return r

def compiled_diagnostic(native):
    proc,client,log=launch("compiled-diagnostic","compiled",diagnostic=True)
    r={"status":"started","selected":SELECTED}
    try:
        ledger=client.command("functioncompiler ir016 "+SELECTED)
        if not ledger.startswith("IR016 function="+SELECTED) or stat(ledger,"typed_lines")<=0:
            raise AssertionError("selected original publisher function did not lower: "+ledger)
        before=client.command("functioncompiler ir008")
        r["event"]=event(client,label="compiled-diagnostic")
        after=client.command("functioncompiler ir008")
        if r["event"]["state"]!=native["event"]["state"]:
            raise AssertionError("native diagnostic state mismatch")
        keys=("executed_regions","executed_steps","fallback_steps","ir039_native_fallbacks",
              "ir040_proofs","ir040_operand_reads_reused","ir040_arithmetic_steps","reentrant_yields")
        r["diagnostics"]={k:stat(after,k)-stat(before,k) for k in keys}
        if r["diagnostics"]["executed_regions"]<=0 or r["diagnostics"]["executed_steps"]<=0:
            raise AssertionError("selected native publisher regions not executed")
        if "..." in ledger:raise AssertionError("cannot join truncated ledger")
        spans=re.findall(r"([JI])([0-9]+):([0-9]+)",ledger.split("layout=",1)[1])
        covered={i for _,start,length in spans for i in range(int(start)-1,int(start)-1+int(length))}
        if len(covered)!=stat(ledger,"typed_lines"):raise AssertionError("ledger region mismatch")
        r["native_observed_eligible_visits"]=sum(int(x["entries"]) for x in native["rows"]
            if x["function"]==SELECTED and int(x["index"]) in covered)
        r["ledger"]=ledger
        r["status"]="accepted"
    finally:
        stop(proc,client,log)
        save("compiled-diagnostic",r)
    raw=(OUT/"compiled-diagnostic.server.log").read_text(errors="replace")
    r["compile_measurements"]=[line.split("IR0",1)[1] for line in raw.splitlines()
        if ("IR041_COMPILE function="+SELECTED+" " in line or "IR042_ADAPTER function="+SELECTED+" " in line)]
    save("compiled-diagnostic",r)
    print("IR042_PUBLISHER_PREFLIGHT "+json.dumps(r),flush=True)
    return r

def timed(label,mode,reference):
    proc,client,log=launch(label,mode)
    r={"label":label,"mode":mode,"warmup":[],"status":"started"}
    try:
        thread=find_server_thread(proc.pid)
        for i in range(2):
            warm=event(client,thread,label+"-warm"+str(i))
            if warm["state"]!=reference:raise AssertionError("warmup parity")
            r["warmup"].append(warm)
        warm_cost=[x["cpu_ns_per_tick"] for x in r["warmup"]]
        r["warmup_spread"]=abs(warm_cost[0]-warm_cost[1])/stats.mean(warm_cost)
        if r["warmup_spread"]>AA_LIMIT:
            r["status"]="warmup_unqualified"
            return r
        r["measurement"]=event(client,thread,label+"-measured")
        if r["measurement"]["state"]!=reference:raise AssertionError("event parity")
        r["status"]="complete"
        return r
    finally:
        stop(proc,client,log)
        save(label,r)
        print("IR042_PUBLISHER_ARM "+json.dumps({k:v for k,v in r.items() if k!="warmup"}),flush=True)

def reduction(a,b):return 1-b["measurement"]["cpu_ns_per_tick"]/a["measurement"]["cpu_ns_per_tick"]

def main():
    global NATIVE_TARGETS,CALLEE_TARGETS,SELECTED
    OUT.mkdir(parents=True,exist_ok=True)
    publisher=base.original_publisher()
    pack=Pack("blastback",base.PACK,base.PIN)
    NATIVE_TARGETS,CALLEE_TARGETS=allowlists(pack)
    r={"status":"started","publisher":publisher,"timed_arms":[],"production_promotion":False}
    try:
        native=native_census(pack)
        r["census_summary"]=native["summary"]
        candidates=[x for x in native["summary"]["functions"] if x.get("candidate_region_entries",0)>0]
        if not candidates:
            r["status"]="no_exercised_candidate"
            return
        SELECTED=candidates[0]["function"]
        r["selected"]=SELECTED
        diag=compiled_diagnostic(native)
        r["compiled_diagnostic"]=diag
        reference=native["event"]["state"]
        for label,mode in (("A0","native"),("A1","native")):
            r["timed_arms"].append(timed(label,mode,reference))
            save("results",r)
        aa=r["timed_arms"]
        if any(x["status"]!="complete" for x in aa) or abs(reduction(*aa))>AA_LIMIT:
            r["status"]="publisher_native_aa_unqualified"
            return
        r["initial_aa"]=reduction(*aa)
        for label,mode in (("A2","native"),("B1","compiled"),("B2","compiled"),("A3","native")):
            r["timed_arms"].append(timed(label,mode,reference))
            save("results",r)
        a,b,c,d=r["timed_arms"][2:]
        if any(x["status"]!="complete" for x in (a,b,c,d)):
            r["status"]="publisher_treatment_warmup_unqualified"
            return
        aa_max=max(abs(r["initial_aa"]),abs(reduction(a,d)),abs(reduction(b,c)))
        reductions=[reduction(a,b),reduction(d,c)]
        r["summary"]={"max_aa":aa_max,"reductions":reductions,
            "median_reduction":stats.median(reductions),
            "pilot_gate_pass":aa_max<=AA_LIMIT and min(reductions)>=max(MIN_REDUCTION,2*aa_max),
            "scope":"one original publisher event, one selected function, server CPU per publisher tick",
            "general_datapack_speedup":False}
        r["status"]="complete"
    except BaseException as e:
        r.update(status="invalid",error=repr(e))
        raise
    finally:
        save("results",r)
        print("IR042_PUBLISHER_SUMMARY "+json.dumps({k:v for k,v in r.items() if k not in
            ("timed_arms","compiled_diagnostic","publisher")}),flush=True)
if __name__=="__main__":main()
