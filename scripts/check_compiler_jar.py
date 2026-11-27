#!/usr/bin/env python3
"""Inspect actual built JAR, not just source selection."""
import json, pathlib, sys, zipfile
root=pathlib.Path(__file__).resolve().parents[1]
fixture=sys.argv[1]=="fixture"
jars=[p for p in (root/"build/libs").glob("*.jar") if not p.name.endswith("-sources.jar")]
assert len(jars)==1,jars
with zipfile.ZipFile(jars[0]) as z:
    names=z.namelist()
    mod=json.loads(z.read("fabric.mod.json"))
    cfg=json.loads(z.read("function_compiler.mixins.json"))
    assert "plugin" not in cfg
    prefix="dev/functioncompiler/"
    for name in ("CompilerForkPlan024","CompilerForkExecutor025","CompilerForkBytecode025",
                 "IR036CostModel","TypedIREffectAnalysis","ScoreValueRevisionAccess","mixin/ScoreValueRevisionMixin"):
        assert prefix+name+".class" not in names,name
    for name in ("ReentrantQueueProbe","mixin/ScoreLifecycleFixtureMixin",
                 "mixin/ScoreboardQueueInjectionMixin","mixin/IntegrationMixinPlugin"):
        assert (prefix+name+".class" in names)==fixture,name
    assert ("function_compiler.fixtures.mixins.json" in names)==fixture
    assert ("function_compiler.fixtures.mixins.json" in mod["mixins"])==fixture
    assert ("-fixtures" in mod["version"])==fixture
    commands=z.read(prefix+"CompilerFixtures.class")
    for token in (b"fc_ir040_batch",b"fc_ir046_callback",b"fc_probe_leaf"):
        assert (token in commands)==fixture,token
print("INTEGRATION_JAR",json.dumps({"jar":jars[0].name,"fixture":fixture,"status":"accepted"}))
