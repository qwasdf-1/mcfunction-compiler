"""IR-026 original pinned Blastback source and exact-function compilation gate."""
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
import ci_typed_ir026_blastback as i

class IR026OriginalPublisherContracts(unittest.TestCase):
    def test_exact_unchanged_original_pack_and_source_slot(self):
        self.assertEqual(i.MODES,("native","plan_only","compiled"))
        self.assertEqual(i.PIN,
            "8578ad9f277a8d8c1e5a1aba50b3f36f624f009a61beb33441d8c59494597b90")
        self.assertEqual(i.TARGET,"erb:restore/job_tick")
        self.assertEqual(i.EXPECTED_SOURCE_INDEX,4)
        self.assertEqual(i.WINDOW_SECONDS,30)
        self.assertTrue(i.EXACT_ORIGINAL_LINE.startswith(
            "execute as @e[type=minecraft:marker,tag=erb.block,tag=!erb.verified]"))
        runner=(ROOT/"scripts/ci_typed_ir026_blastback.py").read_text()
        for token in ("hashlib.sha256(data).hexdigest()","commands[EXPECTED_SOURCE_INDEX]",
                      "commands.count(EXACT_ORIGINAL_LINE)!=1",
                      "shutil.copyfile(PACK,dest)",
                      "hashlib.sha256(dest.read_bytes()).hexdigest()!=PIN",
                      "write_setup_pack(","original_datapack_unchanged",
                      "full_restoration_claim","performance_claim"):
            self.assertIn(token,runner)
        self.assertNotIn("archive.writestr(",runner)

    def test_exact_function_gate_emits_fork_even_without_adjacent_typed_lines(self):
        typed=(ROOT/"src/main/java/dev/functioncompiler/TypedScoreIR.java").read_text()
        self.assertIn('System.getenv("FC_TYPED_IR_FUNCTION_FILTER")',typed)
        self.assertIn("FUNCTION_FILTER.equals(id.toString())",typed)
        self.assertIn("mixed.typedRegionCount() == 0 && mixed.compiledForkCount() == 0",typed)
        self.assertIn("mixed.executableEntries()",typed)
        mixed=(ROOT/"src/main/java/dev/functioncompiler/MixedFunctionIR.java").read_text()
        self.assertIn("CompilerForkExecutor025.compile(plan, entry)",mixed)
        self.assertIn("index, plan, generated, true",mixed)
        self.assertIn("nodes.stream().anyMatch(n -> !(n instanceof TypedRegion t)",mixed)

    def test_disable_unrelated_mutators_preserve_plan_and_control(self):
        for mode in i.MODES:
            env=i.options(mode)
            for key,value in i.DISABLED_FLAGS.items():
                self.assertEqual(env[key],value)
            self.assertEqual(env["FC_TYPED_IR_FUNCTION_FILTER"],
                             i.TARGET if mode!="native" else "")
            self.assertEqual(env["FC_TYPED_IR_COMPILED_FORK"],str(mode=="compiled").lower())
            self.assertEqual(env["FC_TYPED_IR_NATIVE_FORK_PLAN"],
                             str(mode!="native").lower())
            self.assertEqual(env["FC_TYPED_IR_REENTRANT_SAFE"],"true")
            self.assertEqual(env["FC_TYPED_IR_MODE"],
                             "bytecode" if mode!="native" else "")
        self.assertEqual(i.MAX_TICK_EXPOSURE_RATIO,1.50)
        self.assertGreaterEqual(i.MIN_TICKS,100)
        self.assertEqual(len(i.WITNESSES),5)
        self.assertEqual(len(i.MARKERS),3)
        self.assertIn("needs_restore",[x[0] for x in i.SCORES])
        self.assertIn("active_job",[x[0] for x in i.SCORES])

    def test_real_original_event_execution_is_required(self):
        runner=(ROOT/"scripts/ci_typed_ir026_blastback.py").read_text()
        for token in (
            "compiled_forks","executed_forks","selector_scans",
            "selected_sources","native_marker_counts",
            "bounded_witness_parity","template_equal",
            "marker_counts","tick_delta",
            "original_target_source","MAX_TICK_EXPOSURE_RATIO",
            "event_tnt_remaining","source_compiler_ledger",
            '"C5:1"', '"N5:1"', "if remaining!=0:",
            "complete_restoration_claim","speedup_claim",
        ):
            self.assertIn(token,runner)

if __name__=="__main__":unittest.main()
