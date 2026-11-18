"""Synthetic correctness contracts for compiler-coverage source audit."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from audit_compiler_coverage import audit, line_classification, markdown
from run_specialization_inventory import Pack


class CoverageAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix="compiler-audit-")
        cls.archive=Path(cls.temp.name)/"synthetic.zip"
        with zipfile.ZipFile(cls.archive,"w") as z:
            z.writestr("data/minecraft/tags/function/tick.json",
                       json.dumps({"values":["demo:tick"]}))
            z.writestr("data/demo/function/tick.mcfunction", "\n".join([
                "scoreboard players add #counter probe 1",
                "execute as @e[tag=coal] run scoreboard players add #counter probe 1",
                "execute if score #counter probe matches 1 run scoreboard players set #counter probe 2",
                "function demo:macro with entity @s data",
                "function demo:leaf",
                "say end",
            ]))
            z.writestr("data/demo/function/macro.mcfunction",
                       "$scoreboard players add #counter probe $(step)\n")
            z.writestr("data/demo/function/leaf.mcfunction",
                       "scoreboard players reset #counter probe\n")
            z.writestr("data/demo/function/unreachable.mcfunction",
                       "execute store result storage never:x path int 1 run say hi\n")
        cls.sha=hashlib.sha256(cls.archive.read_bytes()).hexdigest()
        cls.pack=Pack("synthetic",cls.archive,cls.sha)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_exact_function_and_class_conservation(self):
        r=audit(self.pack)
        self.assertEqual(r["command_lines_scanned"],8)
        self.assertEqual(r["functions_reachable_or_scheduled"],3)
        self.assertEqual(r["functions_unreachable_from_known_tags"],1)
        self.assertEqual(r["macro_with_provider_counts"],{"entity":1})
        self.assertEqual(r["classification_counts"]["lexically_forked_execute"],1)
        self.assertEqual(
            sum(r["classification_counts"].values()),r["command_lines_scanned"])
        self.assertFalse(
            any(row["id"]=="demo:unreachable"
                for row in r["functions_review_ranked"]))

    def test_labels_are_candidates_not_runtime_claims(self):
        r=audit(self.pack)
        self.assertIn("Static",r["interpretation"]["no_runtime_claim"])
        self.assertTrue(all(row["candidate_only"] for row in (
            line_classification(self.pack,"scoreboard players add #x p 1"),
            line_classification(self.pack,"function demo:macro with storage demo:state"),
            line_classification(self.pack,"execute as @e run say hi"),
        )))
        self.assertEqual(
            line_classification(self.pack,
               "function demo:macro with storage demo:state")["macro_with_provider"],
            "storage")

    def test_quoted_execute_tokens_do_not_create_fake_forks(self):
        c=line_classification(self.pack,'execute if score #x p matches 1 run say "as at on"')
        self.assertTrue(c["execute_wrapped"])
        self.assertFalse(c["forked_lexically"])

    def test_forked_context_rejected_for_static_fusion(self):
        c=line_classification(self.pack,
            "execute as @e[type=minecraft:zombie] run scoreboard players add #x p 1")
        self.assertTrue(c["forked_lexically"])
        self.assertEqual(c["category"],"lexically_forked_execute")

    def test_existing_state_machine_parsers_are_not_mislabeled_vanilla(self):
        for command in ("tag @s add test", "kill @e[tag=test]", "tp @s ~ ~ ~"):
            with self.subTest(command=command):
                c=line_classification(self.pack,command)
                self.assertEqual(c["category"],"known_parser_root_not_proven")
                self.assertTrue(c["candidate_only"])

    def test_report_includes_noncausal_warning(self):
        m=markdown(audit(self.pack))
        self.assertIn("not an estimate",m)
        self.assertIn("review",m.lower())
        self.assertIn("selective",m.lower())

if __name__=="__main__":
    unittest.main()
