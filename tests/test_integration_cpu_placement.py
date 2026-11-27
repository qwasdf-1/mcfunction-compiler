"""Placement contracts do not require a particular CI CPU topology."""
import unittest
from scripts.integration_cpu_placement import parse_cpu_list, choose_affinity, delta

class Placement(unittest.TestCase):
    def test_parse_sparse_ranges(self):
        self.assertEqual(parse_cpu_list("0-2,4,8-9"),{0,1,2,4,8,9})
    def test_reserves_visible_smt_siblings(self):
        self.assertEqual(choose_affinity({0,1,2,3},{0:{0,2},1:{1,3},2:{0,2},3:{1,3}}),
                         (3,[1,3],[0,2]))
    def test_prefers_other_cores(self):
        siblings={i:{i,i+4} for i in range(4)} | {i:{i,i-4} for i in range(4,8)}
        self.assertEqual(choose_affinity(set(range(8)),siblings),(7,[3,7],[0,1,2]))
    def test_rejects_insufficient_topology(self):
        with self.assertRaises(RuntimeError):choose_affinity({0,1},{})
        with self.assertRaises(RuntimeError):choose_affinity({0,1,2,3},{3:{0,1,2,3}})
    def test_unavailable_not_zero(self):
        b={"migrations":None,"cpu_times_ticks":{"idle":1}}
        a={"migrations":None,"cpu_times_ticks":{"idle":3,"steal":4}}
        self.assertIsNone(delta(b,a)["server_migrations"])
        self.assertEqual(delta(b,a)["cpu_times_ticks_delta"],{"idle":2})
if __name__=="__main__":unittest.main()
