#!/usr/bin/env python3
"""Production build: real opt-in profile, explicit disabled/missing namespace control."""
import json, os
import ci_typed_ir017 as base
from ci_typed_ir013 import stat

OUT=base.ROOT/"build/reports/INTEGRATION-001-PROFILE"
base.OUT=OUT
base.FUNCTIONS={"profile_smoke":["scoreboard players add #x fc_ir 1"]*8}
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for k in list(os.environ):
        if k.startswith("FC_") or k=="ORG_GRADLE_PROJECT_fcIntegrationFixtures":del os.environ[k]
    rows={}
    for arm in ("off","missing_namespace","validated"):
        base.options=lambda mode:({} if arm=="off" else
            {"FC_TYPED_COMPILER_PROFILE":"validated","FC_TYPED_IR_DIAGNOSTICS":"true",
             **({"FC_TYPED_IR_NAMESPACE":"fc_ir"} if arm=="validated" else {})})
        p,c,l=base.start("native")
        try:
            status=c.command("functioncompiler status")
            assert "fixture_build=false" in status,status
            assert ("typed_profile=validated" in status)==(arm=="validated"),status
            assert ("wrapper_enabled=true" in status)==(arm=="validated"),status
            fixture_reply=c.command("fc_ir040_batch wrap_pure 1")
            assert "IR040_BATCH" not in fixture_reply,fixture_reply
            c.command("scoreboard players set #x fc_ir 0")
            before=c.command("functioncompiler ir008")
            c.command("function fc_ir:profile_smoke")
            after=c.command("functioncompiler ir008")
            state=base.nullable_score(c,"#x","fc_ir")
            assert state==8,state
            if arm=="validated":
                assert stat(after,"compiled_regions")>0,after
                assert stat(after,"executed_regions")-stat(before,"executed_regions")==1,after
                assert stat(after,"executed_steps")-stat(before,"executed_steps")==8,after
            else: assert "disabled" in after,after
            rows[arm]={"status":status,"state":state,"diagnostic":after,"fixture_reply":fixture_reply}
        finally:
            base.stop(p,c,l)
            (OUT/"native.server.log").rename(OUT/(arm+".server.log"))
    (OUT/"results.json").write_text(json.dumps({"status":"accepted","arms":rows},indent=2)+"\n")
    print("INTEGRATION_PROFILE accepted")
if __name__=="__main__":main()
