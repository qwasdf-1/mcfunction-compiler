"""IR-032 moving-source and exact execution-census parser tests."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_ir032_dynamic_lights_census import NAMESPACE, TARGETS, parse_exec_census
from run_dynamic_lights_profile import entity_position, item_motion


class FakeRcon:
    def __init__(self, response):
        self.response = response

    def command(self, command):
        self.command_seen = command
        return self.response


class IR032DynamicLightsRunnerTests(unittest.TestCase):
    def test_entity_position_parses_snbt_doubles(self):
        rcon = FakeRcon("The data of entity abc is [1.25d, 65.0d, -2.5d]")
        self.assertEqual(entity_position(rcon, 7), (1.25, 65.0, -2.5))
        self.assertIn("tag=fc_dl_7", rcon.command_seen)

    def test_entity_position_rejects_missing_entity(self):
        with self.assertRaisesRegex(RuntimeError, "Could not parse position"):
            entity_position(FakeRcon("No entity was found"), 0)

    def test_motion_vectors_keep_each_source_near_its_player(self):
        vectors = [item_motion(index) for index in range(24)]
        self.assertEqual(len(vectors), 24)
        self.assertEqual(vectors[0], (0.35, 0.12))
        self.assertEqual(vectors[8], (-0.35, 0.12))
        self.assertEqual(vectors[12], (0.35, -0.12))
        self.assertEqual(vectors[20], (-0.35, -0.12))


class IR032ExecutionCensusParserTests(unittest.TestCase):
    def sample_log(self):
        rows = []
        for index, target in enumerate(TARGETS):
            rows.append(
                f"FC_EXEC_ROW function={NAMESPACE}:{target} index=0 "
                "entries=3 callbacks=3 kind=plain dispatch_shape=normal input=none"
            )
        return [
            f"FC_EXEC_BEGIN namespace={NAMESPACE} sites={len(TARGETS)} "
            "entries=45 callbacks=45 overflow=0 "
            f"targets={len(TARGETS)} callees=2 native_calls=10",
            *rows,
            f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tick native_call_tasks=4",
            f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tickcheck native_call_tasks=6",
            f"FC_EXEC_END namespace={NAMESPACE} entries=45 callbacks=45 native_calls=10",
        ]

    def test_reconciles_all_target_sites_and_callee_calls(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "census.log"
            path.write_text("\n".join(self.sample_log()), encoding="utf-8")
            result = parse_exec_census(
                path,
                [f"{NAMESPACE}:internal/tick", f"{NAMESPACE}:internal/tickcheck"],
            )
        self.assertEqual(result["summary"]["sites"], str(len(TARGETS)))
        self.assertEqual(result["total_function_call_tasks"], 10)
        self.assertEqual(set(result["target_functions_observed"]),
                         {f"{NAMESPACE}:{target}" for target in TARGETS})

    def test_rejects_unreconciled_native_call_count(self):
        lines = self.sample_log()
        lines[-2] = f"FC_EXEC_CALLEE function={NAMESPACE}:internal/tickcheck native_call_tasks=5"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "census.log"
            path.write_text("\n".join(lines), encoding="utf-8")
            with self.assertRaisesRegex(AssertionError, "do not reconcile"):
                parse_exec_census(
                    path,
                    [f"{NAMESPACE}:internal/tick", f"{NAMESPACE}:internal/tickcheck"],
                )


if __name__ == "__main__":
    unittest.main()
