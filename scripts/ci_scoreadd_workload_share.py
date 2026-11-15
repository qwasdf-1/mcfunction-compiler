#!/usr/bin/env python3
"""SCHED-COMP-020: diagnose actual ScoreAdd reach and Amdahl dilution in Vein Miner.

Three independent, non-comparable JVMs for:
  1. optimizer-off reference, no counters, true Server-thread CPU;
  2. cached ScoreAdd reference, no counters, true Server-thread CPU;
  3. typed ScoreAdd with BOTH execution and ordinary-callback counters;
All three use exactly the same playerbot/native 215-block Vein Miner event.
Counts are NEVER converted into CPU fractions; an independent
sampling profiler can follow only if these counts justify one. No significance inference
from one unpaired CPU reference per arm, and no performance promotion.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/"build"/"benchmarks"/"SCHED-COMP-020"
PACK=ROOT/"references/real-world/candidates/VeinMiner-5.3.0+26.3.zip"
EXPECTED_PACK_SHA="fa5fbfc08b54a881ec1cf255fdc2e7714c258e451d17c626309cbf5988df6e4e"
ARMS=(
    ("off_cpu","off",False,False),
    ("cached_cpu","score-add",False,False),
    ("compiled_counter","score-add-instrumented",True,False),
)
STATE_FIELDS=(
    "player_mined_source_stat","work_after","work_expected",
    "run_state_after","queue_head_delta","remaining_ore",
    "source_block_remains","operation_markers_after","target_markers_after",
)
WORK_EXPECTED=215
QUEUE_STEPS_EXPECTED=1952


def verify_pack()->str:
    digest=hashlib.sha256(PACK.read_bytes()).hexdigest()
    if digest!=EXPECTED_PACK_SHA:
        raise AssertionError(f"Different publisher pack: {digest}")
    return digest


def run_native(arm:str,mode:str,count:bool,spark:bool)->dict:
    stage=OUT/f"premining-{arm}.json"
    command=[
        sys.executable,str(ROOT/"scripts/run_veinminer_profile.py"),
        "--stack","fabric","--compiler-mode",mode,
        "--side","6","--capture-timeout","150",
        "--setup-rcon-timeout-seconds","45",
        "--startup-readiness-record",str(stage),
        "--tick-stability-diagnostics","--pre-event-idle-seconds","9",
        "--capture-server-thread-cpu",
    ]
    if not spark:command.append("--no-spark")
    if count:
        command.extend(("--count-command-callbacks","--scoreadd-path-coverage-diagnostic"))
    environment=dict(os.environ)
    environment.pop("GRADLE_RO_DEP_CACHE",None)
    environment["GRADLE_USER_HOME"]=str(OUT/"gradle-user-home")
    environment.pop("FC_SCORE_ADD_LEGACY_NAMESPACE",None)
    result=subprocess.run(command,cwd=ROOT,env=environment,
                          text=True,stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,timeout=750,check=False)
    (OUT/f"{arm}.stdout.log").write_text(result.stdout,encoding="utf-8")
    (OUT/f"{arm}.stderr.log").write_text(result.stderr,encoding="utf-8")
    if result.returncode:
        raise RuntimeError(
            f"{arm} native event failed; exit={result.returncode}; "
            f"stderr={result.stderr[-2600:]!r};stdout={result.stdout[-1000:]!r}")
    payload=json.loads(result.stdout)
    data=payload["results"]
    if (data.get("compiler_mode")!=mode or
        not data.get("valid_native_workload") or
        data.get("work_expected")!=WORK_EXPECTED or
        data.get("queue_head_delta")!=QUEUE_STEPS_EXPECTED or
        data.get("run_state_after")!=0):
        raise AssertionError(f"{arm} failed exact event/queue parity")
    if not data.get("tick_pre_event_stability",{}).get("stable"):
        raise AssertionError(f"{arm} did not pass pre-event idle stability")
    cpu=data.get("server_thread_event_cpu")
    if not isinstance(cpu,dict) or not cpu.get("cpu_measurement_valid"):
        raise AssertionError(f"{arm} has no Server-thread CPU identity")
    if not cpu.get("host_quality_pass"):
        raise AssertionError(f"{arm} has unstable host CPU/runqueue quality")
    compiled=data.get("queue_score_add_compiled")
    if mode=="off" and compiled not in (None,0):
        raise AssertionError(f"Off arm specialized commands: {compiled}")
    if mode!="off" and (not isinstance(compiled,int) or compiled<=0):
        raise AssertionError(f"{arm} has no compiled ScoreAdd candidates")
    if spark:
        if (not data.get("spark_capture_enabled") or
            not data.get("server_thread_stack_node_count")):
            raise AssertionError("Missing Spark Server-thread sampled coverage")
    if count:
        if not data.get("valid_scoreadd_path_coverage_diagnostic"):
            raise AssertionError("Independently scoped ScoreAdd/callback entry diagnostic invalid")
    return {
        "arm":arm,"mode":mode,"counter_instrumentation":count,
        "spark_instrumentation":spark,"source_output":payload.get("output"),
        "pinned_pack":data["datapack_sha256"],
        "native_state":{k:data[k] for k in STATE_FIELDS},
        "work_exact":True,
        "queue_score_add_compiled":compiled,
        "queue_score_add_executed_delta":data.get("queue_score_add_executed_delta"),
        "ray_score_add_executed_delta":data.get("ray_score_add_executed_delta"),
        "global_score_add_executed_delta":data.get("score_add_executed_delta"),
        "valid_scoreadd_path_coverage_diagnostic":
            data.get("valid_scoreadd_path_coverage_diagnostic"),
        "callback_metrics":data.get("command_callback_metrics"),
        "event_cpu":cpu,
        "event_seconds":data.get("operation_completion_seconds"),
        "tick_diagnostics":data.get("tick_post_event_diagnostic"),
    }


def interpret(records:dict)->dict:
    if set(records)!={x[0] for x in ARMS}:
        raise AssertionError(f"Missing independent diagnostic arms: {set(records)}")
    state={json.dumps(r["native_state"],sort_keys=True) for r in records.values()}
    packs={r["pinned_pack"] for r in records.values()}
    if len(state)!=1 or packs!={EXPECTED_PACK_SHA}:
        raise AssertionError("Different ore work or publisher pack across arms")
    instrumented=records["compiled_counter"]
    callbacks=instrumented["callback_metrics"]
    if not isinstance(callbacks,dict):
        raise AssertionError("No ordinary callback instrumentation")
    optimized=callbacks["optimized_score_add_leaf_callbacks"]
    generic=callbacks["generic_leaf_callbacks"]
    tracked=callbacks["score_add_executed_counter_delta"]
    all_leaf=callbacks["total_ordinary_leaf_callbacks"]
    entries=callbacks["typed_score_add_callback_entries"]
    scoped=callbacks["typed_score_add_callback_entries_in_scope"]
    drain=instrumented["queue_score_add_executed_delta"]
    ray=instrumented["ray_score_add_executed_delta"]
    compiled=instrumented["queue_score_add_compiled"]
    # The queue's four *actual compiled commands* each execute on all 1,952
    # queue steps. Neither that count nor a nested Brigadier leaf-wrapper
    # count is identical to the single queue-head advancement count.
    expected_queue=QUEUE_STEPS_EXPECTED*compiled
    if (not all(type(n) is int for n in (
            optimized,generic,tracked,all_leaf,entries,scoped,drain,ray,compiled
        )) or compiled!=4 or drain!=expected_queue or ray<=0
        or tracked<drain+ray or tracked!=instrumented["global_score_add_executed_delta"]
        or all_leaf!=optimized+generic or generic<0
        or not (0<optimized<=scoped<=entries and 0<tracked<=entries)
        or instrumented["valid_scoreadd_path_coverage_diagnostic"] is not True):
        raise AssertionError(
            f"Incompatible real ScoreAdd execution path accounting: "
            f"callbacks={callbacks}, queue={drain}, ray={ray}, compiled={compiled}"
        )
    cpu_off=records["off_cpu"]["event_cpu"]["server_thread_cpu_running_ns"]
    cpu_cached=records["cached_cpu"]["event_cpu"]["server_thread_cpu_running_ns"]
    if cpu_off<=0 or cpu_cached<=0:
        raise AssertionError("Nonpositive independent uninstrumented Server-thread CPU")
    return {
        "diagnostic_valid":True,
        "event_state_consistent":True,
        "diagnostic_only":True,
        "actual_successful_typed_scoreadd_executions":tracked,
        "actual_typed_scoreadd_callback_entries":entries,
        "actual_typed_scoreadd_entries_in_queue_callback_scope":scoped,
        "actual_typed_scoreadd_entries_outside_scope":entries-scoped,
        "successful_typed_callbacks_minus_entries":tracked-entries,
        "directly_wrapped_optimized_leaf_callbacks":optimized,
        "scoped_typed_entries_not_seen_as_direct_optimized_leaf":scoped-optimized,
        "queue_drain_scoreadd_executions":drain,
        "queue_scoreadd_compiled_commands":compiled,
        "queue_head_advances":QUEUE_STEPS_EXPECTED,
        "queue_expected_executions":expected_queue,
        "ray_scoreadd_executions":ray,
        "other_function_scoreadd_executions":tracked-drain-ray,
        "ordinary_generic_leaf_callbacks":generic,
        "ordinary_total_leaf_callbacks":all_leaf,
        "scoreadd_fraction_of_observed_ordinary_leaf_callbacks":optimized/all_leaf,
        "direct_leaf_coverage_of_scoped_typed_callback_entries":optimized/scoped,
        "counter_domains":{
            "score_add_executed":"successful typed ScoreAddCommand mutation callbacks in all compiled functions; metrics-enabled, independent of scope",
            "score_add_callback_entries":"all calls entering typed ScoreAddCommand.run, including modifier-delegated and unscoped; diagnostic-only",
            "score_add_callback_entries_in_scope":"typed ScoreAddCommand.run entries while ExecutionContext runCommandQueue callback scope is active, diagnostic-only",
            "optimized_score_add_leaf_callbacks":"instrumented CallbackMetricCommand wrappers directly around ScoreAddCommand in eligible plain-text function Brigadier executable contexts; queue scope only; counts before delegating",
            "generic_leaf_callbacks":"instrumented Brigadier leaf wrappers around other command objects, which may indirectly call typed ScoreAdd; not a disjoint category of all underlying command work",
            "queue_score_add_executed":"typed successful callbacks attributable to vm:queue/drain; four compiled ScoreAdd callbacks per queue head step",
        },
        "limitations_of_fraction":(
            "Only the fraction of instrumented ordinary Brigadier leaf-wrapper"
            " callbacks, NOT the fraction of total underlying typed calls or CPU."
            " Modifier-delegated typed callbacks may be under a generic wrapper,"
            " and unwrapped/custom contexts are outside this denominator."
        ),
        "uninstrumented_cpu_reference_ns":{
            "off":cpu_off,"cached":cpu_cached,
        },
        "required_15pct_whole_event_saving_ns_per_eligible_scoreadd":{
            "relative_to_off_cpu":(0.15*cpu_off)/tracked,
            "relative_to_cached_cpu":(0.15*cpu_cached)/tracked,
        },
        "required_saving_interpretation":(
            "Amdahl budgeting counterfactual: to reduce whole-event CPU by"
            " 15% solely through the observed eligible ScoreAdd invocations,"
            " each must save this many ns on average while every other task"
            " remains unchanged. This is NOT an observed command cost or speedup."
        ),
        "cpu_pair_interpretation":"Two unpaired independent CPU samples are diagnostics, not a supported causal performance result",
    }


def main()->int:
    OUT.mkdir(parents=True,exist_ok=True)
    report=OUT/"diagnostic.json"
    data={
        "study":"SCHED-COMP-020","status":"started",
        "scope":"Separate instrumentation for actual ScoreAdd execution reach and whole-event CPU budget",
        "noncausal":True,
        "arms":[a[0] for a in ARMS],
        "records":{},
    }
    report.write_text(json.dumps(data,indent=2)+"\n")
    try:
        data["publisher_pack_sha256"]=verify_pack()
        for arm,mode,count,spark in ARMS:
            print(f"COMP-020 DIAGNOSTIC ARM {arm}",flush=True)
            data["records"][arm]=run_native(arm,mode,count,spark)
            report.write_text(json.dumps(data,indent=2)+"\n")
        data["analysis"]=interpret(data["records"])
        data["status"]="complete"
        print("SCHED-COMP-020 COMPLETE "+json.dumps(data["analysis"]),flush=True)
    except BaseException as err:
        data["status"]="failed"
        data["error"]=repr(err)
        raise
    finally:
        report.write_text(json.dumps(data,indent=2)+"\n")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
