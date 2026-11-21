"""IR-030 JFR attribution tests: synthetic JFR shapes, no native performance claim."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from ci_typed_ir030_jfr import category_samples, summarize_events, MIN_SAMPLES


def frame(c, m):
    return {"method": {"type": {"name": c}, "name": m}}


def event(tid, frames, state="STATE_RUNNABLE"):
    return {"type": "jdk.ExecutionSample", "values": {
        "sampledThread": {"osThreadId": str(tid)}, "state": state,
        "stackTrace": {"frames": frames},
    }}


class IR030JfrTests(unittest.TestCase):
    def test_read_and_store_are_separate_inclusive_stacks(self):
        read = [
            frame("net.minecraft.advancements.predicates.NbtPredicate", "getEntityTagToCompare"),
            frame("net.minecraft.server.commands.data.EntityDataAccessor", "getData"),
            frame("net.minecraft.server.commands.data.DataCommands", "getSingleTag"),
        ]
        store = [
            frame("net.minecraft.world.entity.Entity", "load"),
            frame("net.minecraft.server.commands.data.EntityDataAccessor", "setData"),
            frame("net.minecraft.server.commands.ExecuteCommand", "lambda$storeData$0"),
        ]
        a = category_samples([("net.minecraft.server.commands.data.DataCommands", "getSingleTag"),
                              ("net.minecraft.server.commands.data.EntityDataAccessor", "getData")])
        self.assertIn("read_with_serialization", a)
        self.assertNotIn("outer_store_callback", a)
        events = ([event(123, read)] * 150
                  + [event(123, store)] * 50
                  + [event(42, read)] * 500
                  + [event(123, read, "STATE_WAITING")])
        d = summarize_events(events, 123)
        self.assertEqual(d["server_thread_runnable_samples"], 200)
        self.assertAlmostEqual(d["fractions_inclusive"]["read_command"], .75)
        self.assertAlmostEqual(d["fractions_inclusive"]["outer_store_callback"], .25)
        self.assertAlmostEqual(d["fractions_inclusive"]["entity_set_data"], .25)
        self.assertAlmostEqual(d["fractions_inclusive"]["entity_serialization"], .75)
        self.assertTrue(d["fraction_categories_overlap"])

    def test_empty_and_wrong_tid_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Only 0 runnable"):
            summarize_events([event(999, [])] * MIN_SAMPLES, 123)

    def test_more_than_min_samples_required(self):
        with self.assertRaisesRegex(AssertionError, "Only 199 runnable"):
            summarize_events([event(123, [frame("a", "b")])] * (MIN_SAMPLES - 1), 123)

    def test_all_other_minecraft_samples_rejected(self):
        with self.assertRaisesRegex(AssertionError, "Neither original"):
            summarize_events([event(123, [frame("net.minecraft.server.MinecraftServer", "tickServer")])] * MIN_SAMPLES, 123)


if __name__ == "__main__":
    unittest.main()
