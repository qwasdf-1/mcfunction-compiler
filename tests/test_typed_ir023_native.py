"""IR-023: passive native mutation census contracts and fail-closed log parser."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir023_native as ir


def log(mode="plain",changes=False):
    d={m:0 for m in ir.METRICS}
    if changes:
        d.update({
            "add_block_attempt":4,"add_block_changed":3,"add_block_noop":1,
            "add_verified_attempt":2,"add_verified_changed":2,
            "remove_verified_attempt":1,"remove_verified_changed":1,
            "eligible_entered":4,"eligible_left":2,
            "marker_manager_added":6,"manager_added_with_block":3,
            "manager_added_eligible":1,
            "marker_tracked":6,"tracked_with_block":3,"tracked_eligible":1,
            "marker_removed":3,"removed_with_block":1,"removed_eligible":1,
            "removed_killed":1,"removed_discarded":2,
        })
    return "\n".join(["FC_CPU023_BEGIN mode="+mode]+
        [f"FC_CPU023_ROW kind={k} count={v}" for k,v in d.items()]+
        ["FC_CPU023_END mode="+mode])


class IR023Contracts(unittest.TestCase):
    def test_parser_accepts_balanced_passive_counters(self):
        rows=ir.parse_cpu023(log(changes=True),"plain")
        self.assertEqual(rows["add_block_changed"],3)
        self.assertEqual(rows["eligible_entered"],4)
        self.assertEqual(sum(rows[f"removed_{r}"] for r in (
            "unloaded_chunk","changed_dimension","killed","discarded","other")),3)
        self.assertTrue(all(v==0 for v in ir.parse_cpu023(log("control"),"control").values()))

    def test_parser_rejects_inconsistent_metrics(self):
        source=log(changes=True)
        cases=[
            source.replace("add_block_noop count=1", "add_block_noop count=3"),
            source.replace("eligible_entered count=4", "eligible_entered count=9"),
            source.replace("marker_tracked count=6", "marker_tracked count=0"),
            source.replace("removed_discarded count=2", "removed_discarded count=0"),
            source.replace("invalid count=0", "invalid count=1"),
            source.replace("FC_CPU023_END mode=plain",""),
            source.replace("FC_CPU023_ROW kind=add_block_attempt count=4",""),
            source.replace("add_block_attempt count=4","add_block_attempt count=-1"),
        ]
        for item in cases:
            with self.subTest(case=item[-80:]):
                with self.assertRaises(AssertionError):
                    ir.parse_cpu023(item,"plain")

    def test_control_cannot_record_mutations(self):
        with self.assertRaisesRegex(AssertionError,"CONTROL"):
            ir.parse_cpu023(log("control",changes=True),"control")

    def test_exact_native_delegation_no_index_and_explicit_flags(self):
        code=(ROOT/"src/main/java/dev/functioncompiler/CompilerTagMutation023Probe.java").read_text()
        entity=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerTagMutation023EntityMixin.java").read_text()
        manager=(ROOT/"src/main/java/dev/functioncompiler/mixin/CompilerTagMutation023ManagerMixin.java").read_text()
        mixins=(ROOT/"src/main/resources/function_compiler.mixins.json").read_text()
        commands=(ROOT/"src/main/java/dev/functioncompiler/ProbeCommands.java").read_text()
        setup=(ROOT/"scripts/ci_typed_ir019_blastback.py").read_text()
        runner=(ROOT/"scripts/ci_typed_ir023_native.py").read_text()
        for required in (
            '"FC_CPU023_MODE"', '"FC_CPU023_NAMESPACE"', '"erb".equals(NAMESPACE)',
            '"plain".equals(MODE)', '"control".equals(MODE)',
            "entity.entityTags().contains(tag)", "entity instanceof Marker",
            "ENABLED" if False else "enabledFor(entity)",
            "FC_CPU023_BEGIN","FC_CPU023_ROW","FC_CPU023_END"
        ): self.assertIn(required,code)
        for required in (
            'method = "addTag(Ljava/lang/String;)Z"',
            'method = "removeTag(Ljava/lang/String;)Z"',
            'method = "load(Lnet/minecraft/world/level/storage/ValueInput;)V"',
            'method = "setRemoved(Lnet/minecraft/world/entity/Entity$RemovalReason;)V"'
        ): self.assertIn(required,entity)
        for required in ("addEntity(", "startTracking(", "stopTracking(", "cir.getReturnValueZ()"):
            self.assertIn(required,manager)
        for name in ("CompilerTagMutation023EntityMixin","CompilerTagMutation023ManagerMixin"):
            self.assertIn(name,mixins)
        self.assertEqual(commands.count('Commands.literal("cpu023-start")'),2)
        self.assertEqual(commands.count('Commands.literal("cpu023-stop")'),2)
        for required in ('cpu_family=="023"', '"FC_CPU023_MODE"', '"FC_CPU023_NAMESPACE"',
                         '"FC_CPU022_MODE"] = "control"'):
            self.assertIn(required,setup)
        for required in ('cpu_family="023"','functioncompiler cpu023-start',
                         'functioncompiler cpu023-stop',
                         'parse_cpu022(raw_rows,"control")',
                         'original_tag_set_direct_writes_not_observable',
                         '"selector_replacement":False',
                         '"causal_speedup_claim":False',
                         'EXACT_ORIGINAL_LINE','WINDOW_SECONDS','WITNESSES'):
            self.assertIn(required,runner)
        self.assertEqual(ir.MODES,("control","plain"))
        for forbidden in ("ci.cancel()", "ci.setReturnValue(", "queueNext(", "setTags("):
            self.assertNotIn(forbidden,code+entity+manager)


if __name__=="__main__":
    unittest.main()
