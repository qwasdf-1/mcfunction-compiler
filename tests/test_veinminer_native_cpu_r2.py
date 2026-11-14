"""SCHED-COMP-018R2 revised tick stability and independently frozen triplet inference."""
from collections import Counter
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/"scripts"))
import ci_server_event_cpu as proc
import ci_premining_readiness as readiness
import ci_veinminer_native_cpu_r2 as a


def arm(name:str,pair:int,position:int,cpu_ratio:float=1.0,
        latency_ratio:float=1.0,quality:bool=True)->dict:
    return {
        "arm":name,"triplet":pair,"position":position,
        "sha256":a.PACK_SHA256,
        "native_state":{"ore":215,"queue":17},
        "server_thread_cpu_running_ns":int(100_000_000*cpu_ratio),
        "event_completion_seconds":30.0*latency_ratio,
        "cpu_detail":{"host_quality_pass":quality},
        "host_quality":quality,
        "valid_native_workload":True,"valid_activation":True,
        "tick_post_event_diagnostic":{"severe_overload_observed":False},
    }


def campaign(*,off_b_cpu:float=1.0,cached_cpu:float=.93,
             off_b_event:float=1.0,cached_event:float=.99,
             quality:bool=True)->list[dict]:
    result=[]
    for i,order in enumerate(a.plan(),1):
        arms={}
        for p,name in enumerate(order):
            c=1.0 if name=="off_a" else off_b_cpu if name=="off_b" else cached_cpu
            t=1.0 if name=="off_a" else off_b_event if name=="off_b" else cached_event
            arms[name]=arm(name,i,p,c,t,quality)
        result.append({"index":i,"order":list(order),"arms":arms})
    return result


class CPUEventContracts(unittest.TestCase):
    def test_process_tree_finds_exact_server_thread_not_gradle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            def task(pid:int,tid:int,comm:str,children:str="",sched:str=""):
                dir=root/str(pid)/"task"/str(tid)
                dir.mkdir(parents=True,exist_ok=True)
                (dir/"comm").write_text(comm+"\n")
                (dir/"children").write_text(children+"\n")
                (dir/"schedstat").write_text(sched or "6000 2000 5\n")
            task(101,101,"gradle",children="202")
            task(202,202,"java",children="")
            task(202,203,"Server thread",sched="10000000 1000 6\n")
            self.assertEqual(proc.find_server_thread(101,root),(202,203))
            self.assertEqual(proc.read_thread_schedstat(202,203,root)["cpu_running_ns"],10000000)
            task(202,204,"Server thread")
            with self.assertRaises(RuntimeError):proc.find_server_thread(101,root)

    def test_cpu_delta_and_quality(self):
        before={"pid":111,"tid":123,"clock":"linux_schedstat_ns",
                "cpu_running_ns":1000,"runqueue_wait_ns":500,"timeslices":2}
        after={**before,"cpu_running_ns":1001000,"runqueue_wait_ns":100500,
               "timeslices":8}
        result=proc.event_cpu_delta(before,after,10,10)
        self.assertEqual(result["server_thread_cpu_running_ns"],1000000)
        self.assertAlmostEqual(result["server_thread_runqueue_wait_fraction"],1/11)
        self.assertTrue(result["host_quality_pass"])
        noisy=proc.event_cpu_delta(before,after,10,11)
        self.assertFalse(noisy["host_quality_pass"])
        delayed=proc.event_cpu_delta(before,{**after,"runqueue_wait_ns":900500},10,10)
        self.assertFalse(delayed["host_quality_pass"])
        with self.assertRaises(AssertionError):
            proc.event_cpu_delta(before,{**after,"cpu_running_ns":200},10,10)

    def test_throttle_readback_and_unavailable(self):
        with tempfile.TemporaryDirectory() as tmp:
            file=Path(tmp)/"cpu.stat"
            file.write_text("usage_usec 123\nnr_periods 9\nnr_throttled 3\n")
            self.assertEqual(proc.cgroup_throttle_count(file),3)
            self.assertIsNone(proc.cgroup_throttle_count(Path(tmp)/"missing"))

    def test_balanced_frozen_randomization(self):
        p=a.plan()
        self.assertEqual(p,a.plan())
        self.assertEqual(len(p),a.TRIPLETS)
        self.assertTrue(all(set(order)==set(a.MODES) for order in p))
        for mode in a.MODES:
            locations=Counter(order.index(mode) for order in p)
            self.assertEqual(set(locations.values()),{3,4})
        self.assertEqual(len(set(p)),6)

    def test_valid_placebos_and_cpu_gain(self):
        p=a.plan()
        result=a.analyze(campaign(),p)
        self.assertEqual(result["verdict"],"small_gain_supported")
        self.assertEqual(result["event_latency_verdict"],"small_gain_supported")
        self.assertTrue(result["a_a_cpu_interval_includes_zero"])
        self.assertTrue(result["a_a_event_interval_includes_zero"])
        self.assertLess(result["primary"]["exact_median_interval_percent"]["upper"],0)

    def test_both_a_a_controls_must_pass(self):
        p=a.plan()
        self.assertEqual(a.analyze(campaign(off_b_cpu=1.2),p)["verdict"],
                         "invalid_off_off_placebo")
        self.assertEqual(a.analyze(campaign(off_b_event=1.2),p)["verdict"],
                         "invalid_off_off_placebo")

    def test_quality_gate_disqualifies_claim_without_dropping_boot(self):
        p=a.plan()
        records=campaign()
        records[4]["arms"]["cached"]["host_quality"]=False
        analysis=a.analyze(records,p)
        self.assertEqual(analysis["verdict"],"inconclusive_host_quality")
        self.assertEqual(analysis["host_quality_failed_triplets"],[5])
        self.assertEqual(analysis["n_independent_triplets"],a.TRIPLETS)

    def test_wrong_work_and_missing_arm_are_fatal(self):
        p=a.plan()
        records=campaign()
        records[1]["arms"]["off_b"]["native_state"]["ore"]=214
        with self.assertRaises(AssertionError):a.analyze(records,p)
        records=campaign()
        records[1]["arms"].pop("off_b")
        with self.assertRaises(AssertionError):a.analyze(records,p)
        with self.assertRaises(AssertionError):a.analyze(campaign()[:-1],p)

    def test_no_undeclared_order_or_activation(self):
        p=a.plan()
        records=campaign()
        records[1]["order"].reverse()
        with self.assertRaises(AssertionError):a.analyze(records,p)
        records=campaign()
        records[0]["arms"]["cached"]["valid_activation"]=False
        with self.assertRaises(AssertionError):a.analyze(records,p)

    def test_tick_query_parser_matches_real_26_3_responses(self):
        good=("The game is running, but can't keep up with the target tick rate"
              "Target tick rate: 20.0 per second.\n"
              "Average time per tick: 296.9ms (Target: 50.0ms)"
              "Percentiles: P50: 302.1ms P95: 805.2ms "
              "P99: 1264.5ms. Sample: 100")
        tick=proc.parse_tick_query(good)
        self.assertEqual(tick["sample_ticks"],100)
        self.assertAlmostEqual(tick["average_ms"],296.9)
        self.assertAlmostEqual(tick["p95_ms"],805.2)
        self.assertFalse(proc.event_tick_diagnostic(tick)["severe_overload_observed"])
        failed=(good.replace("296.9ms","631.7ms").replace("805.2ms","3073.4ms")
                .replace("1264.5ms","4627.4ms"))
        self.assertTrue(proc.event_tick_diagnostic(
            proc.parse_tick_query(failed))["severe_overload_observed"])
        with self.assertRaises(ValueError):
            proc.parse_tick_query("Unknown gamerule")

    def test_only_idle_baseline_is_a_hard_tick_stability_gate(self):
        idle={"average_ms":55.0,"p50_ms":48.0,"p95_ms":140.0,
              "p99_ms":260.0,"sample_ticks":100}
        self.assertTrue(proc.pre_event_stability(idle)["stable"])
        heavy_during_event={"average_ms":296.9,"p50_ms":302.1,
                            "p95_ms":805.2,"p99_ms":1264.5,
                            "sample_ticks":100}
        self.assertFalse(proc.pre_event_stability(heavy_during_event)["stable"])
        self.assertFalse(proc.event_tick_diagnostic(heavy_during_event)["severe_overload_observed"])
        idle["sample_ticks"]=7
        self.assertFalse(proc.pre_event_stability(idle)["stable"])

    def test_late_tick_overload_is_recorded_not_selected_away(self):
        records=campaign()
        records[1]["arms"]["cached"]["tick_post_event_diagnostic"]["severe_overload_observed"]=True
        result=a.analyze(records,a.plan())
        self.assertEqual(result["verdict"],"small_gain_supported")
        self.assertTrue(result["event_tick_overload_diagnostic_only"])
        self.assertTrue(result["per_triplet"][1]["event_severe_tick_overload"]["cached"])

    def test_rcon_forceload_timeout_is_only_restartable_before_mining(self):
        stage={
            "protocol":readiness.PROTOCOL,
            "stage":readiness.FORCELOAD_STAGE,
            "mining_started":False,
            "stage_history":[
                {"stage":"runner_created","mining_started":False},
                {"stage":"rcon_ready","mining_started":False},
                {"stage":"forceload_pending","mining_started":False},
            ],
        }
        stderr=('Traceback: File "run_veinminer_profile.py" '
                'rcon.command(f"forceload add {x0 - 8} {z0 - 8}") '
                'TimeoutError: timed out')
        self.assertTrue(readiness.retryable_forceload_timeout(1,stderr,stage))
        self.assertTrue(readiness.allowed_retry(1,0,1,stderr,stage))
        self.assertTrue(readiness.allowed_retry(1,1,1,stderr,stage))
        self.assertFalse(readiness.allowed_retry(1,2,1,stderr,stage))
        self.assertFalse(readiness.allowed_retry(2,0,1,stderr,stage))
        self.assertFalse(readiness.retryable_forceload_timeout(0,stderr,stage))
        self.assertFalse(readiness.retryable_forceload_timeout(1,"ValueError",stage))
        self.assertFalse(readiness.retryable_forceload_timeout(1,
            "TimeoutError: timed out during scoreboard work",stage))
        late=dict(stage,stage="mining_packet_started",mining_started=True)
        self.assertFalse(readiness.retryable_forceload_timeout(1,stderr,late))
        corrupted=dict(stage,stage_history=[
            {"stage":"mining_packet_started","mining_started":True},
            {"stage":"forceload_pending","mining_started":False},
        ])
        self.assertFalse(readiness.retryable_forceload_timeout(1,stderr,corrupted))
        wrong=dict(stage,stage="rcon_ready")
        self.assertFalse(readiness.retryable_forceload_timeout(1,stderr,wrong))

    def test_missing_and_corrupt_readiness_records_cannot_authorize_retry(self):
        from pathlib import Path
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"stage.json"
            self.assertIn("invalid_stage_record",readiness.inspect_stage_file(path))
            path.write_text("{not-json")
            self.assertIn("invalid_stage_record",readiness.inspect_stage_file(path))
        self.assertFalse(readiness.allowed_retry(
            1,0,1,'TimeoutError: timed out; rcon.command(f"forceload add',
            {"invalid_stage_record":"unavailable"}))

    def test_campaign_provenance_and_original_018_are_distinct(self):
        self.assertEqual(a.EXPERIMENT,"SCHED-COMP-018R2")
        self.assertEqual(a.TRIPLETS,10)
        self.assertEqual(a.SEED,26874021)
        self.assertEqual(readiness.MAX_RETRIES_PER_PHASE,2)
        self.assertEqual(readiness.SETUP_RCON_TIMEOUT_SECONDS,45)
        self.assertEqual(readiness.EVENT_OBSERVATION_CAP_SECONDS,150)

    def test_predeclared_materiality_and_regression(self):
        p=a.plan()
        self.assertEqual(a.analyze(campaign(cached_cpu=.8),p)["verdict"],
                         "material_gain_supported")
        self.assertEqual(a.analyze(campaign(cached_cpu=1.08),p)["verdict"],
                         "regression_supported")
        self.assertAlmostEqual(a.percent(90,100),-10)
        with self.assertRaises(AssertionError):a.percent(0,100)


if __name__=="__main__":
    unittest.main()
