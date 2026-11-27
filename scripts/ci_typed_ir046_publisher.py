#!/usr/bin/env python3
"""IR046 pinned original wrap diagnostic. No event CPU claim."""
from __future__ import annotations
import json,os,hashlib
from pathlib import Path
import ci_typed_ir042_publisher as pub
from ci_typed_ir013 import stop,stat
from ci_typed_ir046 import KEYS

OUT=pub.base.ROOT/"build/reports/COMPILER-IR-046-PUBLISHER"
TARGET="erb_generated:restore/wrap"
ORIGINAL_OPTIONS=pub.options
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    archive=Path(os.environ["FC_IR046_CENSUS_JSON"])
    census=json.loads(archive.read_text())
    publisher=pub.base.original_publisher()
    pack=pub.Pack("blastback",pub.base.PACK,pub.base.PIN)
    rows=sorted((r for r in census["rows"] if r["function"]==TARGET),key=lambda r:r["index"])
    if len(rows)!=10 or sum(int(r["entries"]) for r in rows)!=172450 or sum(int(r["callbacks"]) for r in rows)!=2:
        raise AssertionError("not the frozen wrap sample")
    for r in rows:
        if pack.functions[TARGET][int(r["index"])][:240]!=r["input"]:raise AssertionError("source mismatch")
    pub.OUT=OUT
    pub.SELECTED=TARGET
    result={"status":"started","target":TARGET,"publisher":publisher,
            "native_archive_sha256":hashlib.sha256(archive.read_bytes()).hexdigest(),
            "native_observed_source_visits":172450,"arms":{},"production_promotion":False}
    try:
        for enabled in (False,True):
            arm="reuse" if enabled else "base"
            def options(mode):
                return ORIGINAL_OPTIONS(mode)|{"FC_TYPED_IR_GUARD_RUN_REUSE":str(enabled).lower(),
                    "FC_TYPED_IR_FUNCTION_FILTER":TARGET,
                    "FC_IR041_COMPILE_TIMING":"false",
                    "FC_TYPED_IR046_TEST_OBSERVER":"false","FC_TYPED_IR046_BENCHMARK":"false"}
            pub.options=options
            proc,client,log=pub.launch(arm,"compiled",diagnostic=True)
            r={"status":"started"}
            result["arms"][arm]=r
            try:
                r["ledger"]=client.command("functioncompiler ir016 "+TARGET)
                if "layout=J1:10" not in r["ledger"] or stat(r["ledger"],"typed_lines")!=10:
                    raise AssertionError("wrap not fully compiled "+r["ledger"])
                before=client.command("functioncompiler ir008")
                r["event"]=pub.event(client,label=arm)
                after=client.command("functioncompiler ir008")
                keys=(*KEYS,"executed_regions","executed_steps","ir039_native_fallbacks","fallback_steps")
                r["runtime_deltas"]={k:stat(after,k)-stat(before,k) for k in keys}
                if r["event"]["state"]!=census["event"]["state"]:
                    raise AssertionError("native restoration mismatch")
                d=r["runtime_deltas"]
                if d["executed_regions"]<=0 or d["executed_steps"]<=0 or d["ir039_native_fallbacks"]:
                    raise AssertionError("actual wrap path not established "+str(d))
                if (d["ir046_boundaries"]>0)!=enabled or (d["ir046_present_reuse"]>0)!=enabled:
                    raise AssertionError("wrong reuse path "+str(d))
                r["status"]="accepted"
            finally:
                stop(proc,client,log)
                pub.save(arm,r)
        result.update(status="accepted",complete_restoration_parity=True,general_datapack_speedup=False)
        print("IR046_PUBLISHER_SUMMARY "+json.dumps({"status":result["status"],"arms":{
            k:{"ledger":v["ledger"],"runtime_deltas":v["runtime_deltas"]} for k,v in result["arms"].items()}}),flush=True)
    except BaseException as e:
        result.update(status="invalid",error=repr(e))
        raise
    finally:pub.save("results",result)
if __name__=="__main__":main()
