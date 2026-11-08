#!/usr/bin/env python3
"""Compare Fabric wrapper modes with mod-free vanilla on Minecraft 26.3."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests" / "runtime"))
from player_bot import PacketIds, PlayerBot  # noqa: E402
from mod_artifacts import MODS, MODS_DIR, STACK_MODS  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = ROOT / "run"
REPORT_DIR = ROOT / "build" / "reports" / "runtime-probe"
RCON_HOST = "127.0.0.1"
RCON_PORT = 25575
RCON_PASSWORD = "function-compiler-runtime-probe"
SERVER_PORT = 25566
RUNTIME_SERVER_JVM_ARGS = ("-Xms512M", "-Xmx2G")
RUNTIME_GRADLE_JVM_ARGS = "-Xmx1G -Dfile.encoding=UTF-8"
LEVEL = "minecraft:max_command_sequence_length"
OBJECTIVE = "fc_probe"
LIFECYCLE_OBJECTIVE = "fc_lifecycle"
PARTNER_LOAD_PACK = "function_compiler_lifecycle_second"
MACRO_WRAPPER_MODES = {
    "score-add-on", "instrument-only", "score-add-timed", "fused-interpreted",
    "bytecode-emitted", "bytecode-compile-failure",
}
HOLDER = "#fcprobe"
LIFECYCLE_PACK = "function_compiler_lifecycle"
QUOTAS = range(0, 8)
DIRECT_FIXTURES = (
    "quota_empty",
    "quota_one",
    "quota_three",
    "quota_execute_four",
    "quota_execute_four_followup",
    "quota_nested_inner",
    "quota_nested_outer",
    "quota_return_value",
    "quota_return_run",
    "quota_return_result",
    "quota_execute_if_function",
    "quota_nested_return_inner",
    "quota_nested_return_outer",
    "quota_recursive",
    "quota_recursive_compiled",
    "quota_change_limit",
    "storage_value_shapes",
    "storage_copy_paths",
    "storage_store_and_errors",
    "mo02_store_result",
    "mo02_store_failures",
    "st02_bossbar_ops",
    "st02_bossbar_values",
    "st06_item_modify",
    "score_holder_and_overflow",
    "score_condition_absent",
    "score_store_targets",
    "leaf_and_tail_runs",
    "predicate_block_tag",
    "predicate_block_state",
    "predicate_item_stack",
    "predicate_item_modifier",
    "state_effect_edges",
    "state_setblock_edges",
    "state_item_slot_edges",
    "state_item_modify_slot_edges",
    "tc02_tail_macro",
    "ct01_return_after_boundary",
    "ct02_store_specialized",
    "ct03_failure_after_mutation",
    "cbx_return_run_fail",
    "cbx_return_run_fail_child",
    "cbx_nested_fail",
    "cbx_unless_success",
    "score_op_store_result",
    "score_op_empty_target",
    "score_op_store_fail",
)
EXTENDED_QUOTA_FIXTURES = frozenset(
    {
        "quota_return_result",
        "quota_execute_four_followup",
        "quota_execute_if_function",
        "quota_nested_return_inner",
        "quota_nested_return_outer",
        "quota_recursive",
        "storage_value_shapes",
        "storage_copy_paths",
        "storage_store_and_errors",
        "mo02_store_result",
        "mo02_store_failures",
        "st02_bossbar_ops",
        "st02_bossbar_values",
        "st06_item_modify",
        "score_holder_and_overflow",
        "score_condition_absent",
        "score_store_targets",
        "leaf_and_tail_runs",
        "predicate_block_tag",
        "predicate_block_state",
        "predicate_item_stack",
        "predicate_item_modifier",
        "state_effect_edges",
        "state_setblock_edges",
        "state_item_slot_edges",
        "state_item_modify_slot_edges",
        "tc02_tail_macro",
        "ct01_return_after_boundary",
        "ct02_store_specialized",
        "ct03_failure_after_mutation",
        "quota_recursive_compiled",
        "quota_change_limit",
        "cbx_return_run_fail",
        "cbx_return_run_fail_child",
        "cbx_nested_fail",
        "cbx_unless_success",
        "score_op_store_result",
        "score_op_empty_target",
        "score_op_store_fail",
    }
)
FORK_LIMITS = tuple(range(1, 13))
FORK_MATCH_COUNTS = (0, 1, 2, 4)
SERVER_JAR_SHA256 = "d052f14d7a173734fba553711e5b570162e2f2a313267ee31a21b975a679be64"
ACTOR_TAG = "fc_probe_actor"
ACTOR_POOL_TAG = "fc_probe_actor_pool"
ACTOR_TYPE = "minecraft:armor_stand"


def configure_probe_ports() -> None:
    """Choose two currently free local ports for this disposable server run."""
    global RCON_PORT, SERVER_PORT

    reservations: list[socket.socket] = []
    try:
        for _ in range(2):
            reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            reservation.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            reservation.bind(("127.0.0.1", 0))
            reservation.listen(1)
            reservations.append(reservation)
        RCON_PORT = reservations[0].getsockname()[1]
        SERVER_PORT = reservations[1].getsockname()[1]
    finally:
        for reservation in reservations:
            reservation.close()

EXPECTED_SCORES = {
    "quota_empty": {quota: 0 for quota in QUOTAS},
    # Observed on the mod-free vanilla arm: 7 from quota 7 (state.count), then
    # 507 from quota 13 (list[1]=50 times weight 10). The third read's fold
    # lands beyond the 0-16 sweep, so the string member is exercised but not
    # observed; see docs/reference/features/command-coverage.md.
    # Observed on the mod-free vanilla arm. The literal player-name holder
    # FCFused reads back 4, and 4 + INT_MAX wraps to -2147483645; the later
    # chain shows INT_MIN - 1 also wrapping. SM-03 + SM-11.
    "score_holder_and_overflow": {
        0: 0, 1: 0, 2: 0, 3: 4, 4: 4, 5: 4,
        6: -2147483645, 7: -2147483645, 8: 3, 9: 3,
        **{quota: -2147483646 for quota in range(10, 17)},
    },
    # Observed on the mod-free vanilla arm. `matches 0..` on an absent score
    # is false (adds nothing), `unless matches 1..` is true (adds 10). The
    # actor-scoped condition contributes nothing because no actor with the
    # fc_cond_actor tag exists in this arm, which is itself the parity signal.
    # SC-03 + SC-05.
    "score_condition_absent": {
        **{quota: 0 for quota in range(0, 8)},
        **{quota: 10 for quota in range(8, 17)},
    },
    # Observed on the mod-free vanilla arm. The store into the initially absent
    # #fresh_store holder writes 5 (the data value), and the actor-scoped store
    # contributes nothing because the fc_cond_actor tag has no actor in this
    # arm - which is the SS-04 parity signal. SS-03 + SS-04.
    "score_store_targets": {
        **{quota: 0 for quota in range(0, 6)},
        **{quota: 5 for quota in range(6, 10)},
        **{quota: 10 for quota in range(10, 17)},
    },
    # Observed on the mod-free vanilla arm: two contiguous leaf calls, then a
    # tail-call run that adds 10 and calls one further leaf. LF-01 + TC-01.
    "leaf_and_tail_runs": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
        6: 6, 7: 8, 8: 10, 9: 12, 10: 24, 11: 36,
        12: 109, 13: 135, 14: 161, 15: 187, 16: 213,
    },
    # Observed on the mod-free vanilla arm. PR-03: tag predicates fold to the
    # same branch outcomes in every arm, and the run stabilises at 89 (= the
    # declared 1,0,1,1,0,0,1) from quota 14, so every case executes.
    "predicate_block_tag": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
        5: 64, 6: 64, 7: 64, 8: 80, 9: 80,
        10: 88, 11: 88, 12: 88, 13: 88,
        14: 89, 15: 89, 16: 89,
    },
    # Observed on the mod-free vanilla arm. PR-04: partial, full, wrong-value
    # and conjunction state predicates fold to the same branch outcomes in every
    # arm, and the run stabilises at 163 (= the declared 1,0,1,0,0,0,1,1) from
    # quota 14, so every case executes.
    "predicate_block_state": {
        0: 0, 1: 0, 2: 0, 3: 0,
        4: 128, 5: 128, 6: 128, 7: 160, 8: 160, 9: 160, 10: 160, 11: 160,
        12: 162, 13: 162, 14: 163, 15: 163, 16: 163,
    },
    # Observed on the mod-free vanilla arm. PR-05: id, item tag, wildcard
    # component presence, component equality and mismatch, an empty slot and a
    # count range all fold to the same branch outcomes in every arm. The run
    # stabilises at 185 (= the declared 1,0,1,1,1,0,0,1) from quota 16, so every
    # case executes; a twelve-case first draft left three cases unexecuted.
    "predicate_item_stack": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
        5: 128, 6: 128, 7: 128,
        8: 160, 9: 160, 10: 176, 11: 176, 12: 184,
        13: 184, 14: 184, 15: 184, 16: 185,
    },
    # Observed on the mod-free vanilla arm. MO-07: the item predicate as an
    # execute modifier, behind an `unless`, in a conjunction with a block
    # predicate, and in a conjunction whose second conjunct fails. The run
    # stabilises at 13 (= the declared 1,1,0,1) from quota 12, so every case
    # executes; item-predicate lines and two-predicate chains cost noticeably
    # more quota than plain scoreboard lines, which is why the fixture is four
    # cases rather than the nine its first draft had.
    "predicate_item_modifier": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
        5: 8, 6: 8, 7: 8,
        8: 12, 9: 12, 10: 12, 11: 12,
        12: 13, 13: 13, 14: 13, 15: 13, 16: 13,
    },
    # Observed on the mod-free vanilla arm. ST-03: the signed-byte amplifier
    # read-back (-1 for the command's 255), the seconds-to-ticks duration edge
    # (600 seconds stored as 12000 ticks), and `effect clear` asserted with
    # `execute unless data`. The run stabilises at 112 (= the declared 1,1,1)
    # from quota 13, so every case executes. The three cases come from one
    # effect given once, because the quota sweep charges each command and the
    # list of active effects is sorted by effect id, so reading two effects
    # from one list would assert index positions rather than the values.
    "state_effect_edges": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
        6: 64, 7: 64, 8: 64, 9: 64,
        10: 96, 11: 96, 12: 96,
        13: 112, 14: 112, 15: 112, 16: 112,
    },
    "state_setblock_edges": {
        0: 0, 1: 0, 2: 0, 3: 0,
        4: 64, 5: 64, 6: 64, 7: 96, 8: 96, 9: 96, 10: 96,
        11: 112, 12: 112, 13: 112, 14: 112, 15: 112, 16: 113,
    },
    # Observed on the mod-free vanilla arm. ST-06: a plain stack in hotbar.0, a
    # counted stack in hotbar.8, the offhand slot, and an empty slot that must
    # not match. The run stabilises at 113 (= the declared 1,1,1,1) from quota
    # 13, so every case executes.
    "state_item_slot_edges": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0,
        5: 64, 6: 64, 7: 64, 8: 96, 9: 96, 10: 96,
        11: 112, 12: 112, 13: 113, 14: 113, 15: 113, 16: 113,
    },
    # Observed on the mod-free vanilla arm. The item-modify half of the slot
    # edges with the confirmed datapack modifier st06_set_count (count=5):
    # hotbar.0 (+64), hotbar.8 (+32) and weapon.offhand (+16) all read back
    # with count=5, and the empty hotbar.5 slot does not match (+1). The
    # modify half costs more quota than the replace half, so the final +1
    # case stays outside the 0-16 sweep and the map tops out at 112; the
    # complete 113 fires only at the high-quota trace, where a modify on the
    # empty slot reports "The target does not have slot hotbar.5" without
    # aborting the remaining function lines.
    "state_item_modify_slot_edges": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0,
        **{quota: 64 for quota in range(6, 10)},
        **{quota: 96 for quota in range(10, 14)},
        **{quota: 112 for quota in range(14, 17)},
    },
    # Observed on the mod-free vanilla arm. TC-02: a plain frame tail-calls a
    # macro function, which tail-calls a second macro function, which tail-calls
    # a plain leaf. The cumulative score is 1 from the caller, +10 from the
    # first macro argument, +20 from the second, and +100 from the leaf; each
    # frame contributes exactly once and the run stabilises at 131 from quota 9.
    "tc02_tail_macro": {
        0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 11, 6: 11, 7: 31, 8: 31,
        9: 131, 10: 131, 11: 131, 12: 131, 13: 131, 14: 131, 15: 131,
        16: 131,
    },
    # Observed on the mod-free vanilla arm. CT-01: an outer frame adds 1, crosses
    # a `say` boundary, adds 10 and 20, then `return run function` calls a child
    # that adds 100, crosses its own boundary, adds 200, and returns 7. Both
    # pending tails (+100 outer, +1000 child) are discarded, so the run
    # stabilises at 331 from quota 9. The response at quotas 10-16 also carries
    # the child's `returned 7`, which the command-response comparison covers.
    "ct01_return_after_boundary": {
        0: 0, 1: 0, 2: 1, 3: 1, 4: 11, 5: 31, 6: 31, 7: 131, 8: 131,
        9: 331, 10: 331, 11: 331, 12: 331, 13: 331, 14: 331, 15: 331,
        16: 331,
    },
    # Observed on the mod-free vanilla arm. CT-02: a `data get` result (7) and an
    # accepted `setblock` success (1) are stored and folded as bits 1,1 = 3. The
    # data branch lands at quota 9 (+2) and the setblock branch at quota 11
    # (+1); the run stabilises at 3 from quota 11. A store that wrote success
    # for the data get would read 1 and leave the map at 1; a setblock that was
    # not preceded by the air reset would read 0 and leave it at 2.
    "ct02_store_specialized": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0,
        9: 2, 10: 2, 11: 3, 12: 3, 13: 3, 14: 3, 15: 3, 16: 3,
    },
    # Observed on the mod-free vanilla arm. CT-03: the parent adds 1, a macro
    # callee adds 10, fails on a missing objective, adds 10 again, the parent
    # adds 100, adds 1000, invokes a macro with a missing key (which contributes
    # nothing), and adds 10000. The run stabilises at 11121 from quota 10, so
    # both completed macro effects and both parent effects apply exactly once.
    "ct03_failure_after_mutation": {
        0: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 11, 6: 11, 7: 21, 8: 121,
        9: 1121, 10: 11121, 11: 11121, 12: 11121, 13: 11121, 14: 11121,
        15: 11121, 16: 11121,
    },
    "storage_value_shapes": {
        **{quota: 0 for quota in range(0, 7)},
        **{quota: 7 for quota in range(7, 13)},
        **{quota: 507 for quota in range(13, 17)},
    },
    # Observed on the mod-free vanilla arm: 33 from quota 8 (copied
    # target.inner[2]), then 143 from quota 14 (target2=11 times weight 10).
    # The removed-element read's fold lands beyond the 0-16 sweep.
    "storage_copy_paths": {
        **{quota: 0 for quota in range(0, 8)},
        **{quota: 33 for quota in range(8, 14)},
        **{quota: 143 for quota in range(14, 17)},
    },
    # Observed on the mod-free vanilla arm: 5 from quota 7 (a successful read
    # of valid), then unchanged. Both absent-path reads leave the score
    # untouched, which is the DS-04/DS-05 oracle: a specialization that let a
    # failing read write a value would show up here.
    "storage_store_and_errors": {
        **{quota: 0 for quota in range(0, 7)},
        **{quota: 5 for quota in range(7, 17)},
    },
    # Observed on the mod-free vanilla arm. MO-02 first half: a result store
    # with byte type and scale 2 turns 200 into (byte)400 = -112, then a
    # success store writes 1s. The run stabilises at 3 (= the declared 1,1)
    # from quota 10, so both cases execute inside the sweep.
    "mo02_store_result": {
        **{quota: 0 for quota in range(0, 6)},
        **{quota: 2 for quota in range(6, 10)},
        **{quota: 3 for quota in range(10, 17)},
    },
    # Observed on the mod-free vanilla arm. MO-02 second half: a failed data
    # get reports result 0 and success false, so both a result store (long 2)
    # and a success store (short 3) overwrite the seed 9 with a zero of the
    # declared type. The run stabilises at 3 (= the declared 1,1) from quota
    # 11, so both cases execute inside the sweep.
    "mo02_store_failures": {
        **{quota: 0 for quota in range(0, 6)},
        **{quota: 2 for quota in range(6, 11)},
        **{quota: 3 for quota in range(11, 17)},
    },
    # Observed on the mod-free vanilla arm. ST-02 first half: bossbar
    # add/remove lifecycle and the unknown-bar edge. The bare remove makes the
    # fixture idempotent (a failing remove on an absent bar does not abort);
    # the add result 1, the value 43 roundtrip and the failing store's 0 land
    # at quotas 6, 11 and 16, so all three cases execute inside the sweep.
    "st02_bossbar_ops": {
        **{quota: 0 for quota in range(0, 6)},
        **{quota: 1 for quota in range(6, 11)},
        **{quota: 3 for quota in range(11, 16)},
        16: 7,
    },
    # Observed on the mod-free vanilla arm. ST-02 second half: the set/get
    # property shapes whose results are the written or read number. The bare
    # leading remove re-creates fresh-bar defaults every iteration, so both
    # set results (43, 200) and the players count 0 land at quotas 8, 12 and
    # 16 - all three cases execute inside the sweep.
    "st02_bossbar_values": {
        **{quota: 0 for quota in range(0, 8)},
        **{quota: 1 for quota in range(8, 12)},
        **{quota: 3 for quota in range(12, 16)},
        16: 7,
    },
    # Observed on the mod-free vanilla arm. ST-06 second half: item modify
    # with a confirmed datapack-defined modifier id. The mainhand reset plus
    # the store around the modify (measured result 1) land case 1 at quota 6;
    # the diamond[count=5] effect read-back lands case 2 at quota 8; the
    # hotbar.8 emerald reset, the bare modify and its effect read-back land
    # case 3 at quota 12, so all three cases execute inside the sweep.
    "st06_item_modify": {
        **{quota: 0 for quota in range(0, 6)},
        **{quota: 1 for quota in range(6, 8)},
        **{quota: 3 for quota in range(8, 12)},
        **{quota: 7 for quota in range(12, 17)},
    },
    "quota_one": {0: 0, 1: 0, **{quota: 1 for quota in range(2, 8)}},
    "quota_three": {0: 0, 1: 0, 2: 1, 3: 2, **{quota: 3 for quota in range(4, 8)}},
    "quota_execute_four": {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: 1,
        5: 2,
        6: 3,
        7: 4,
    },
    "quota_execute_four_followup": {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: 1,
        5: 2,
        6: 3,
        7: 4,
        **{quota: 14 for quota in range(8, 17)},
    },
    "quota_nested_inner": {0: 0, 1: 0, **{quota: 1 for quota in range(2, 8)}},
    "quota_nested_outer": {0: 0, 1: 0, 2: 0, 3: 1, **{quota: 11 for quota in range(4, 8)}},
    "quota_return_value": {0: 0, 1: 0, **{quota: 1 for quota in range(2, 8)}},
    "quota_return_run": {0: 0, 1: 0, 2: 1, **{quota: 11 for quota in range(3, 8)}},
    "quota_return_result": {
        0: 0,
        1: 0,
        2: 0,
        3: 0,
        4: 1,
        **{quota: 17 for quota in range(5, 17)},
    },
    "quota_execute_if_function": {
        0: 0,
        1: 0,
        2: 0,
        3: 1,
        4: 1,
        **{quota: 11 for quota in range(5, 17)},
    },
    "quota_execute_unless_exception": {
        0: 0,
        1: 0,
        2: 1,
        3: 1,
        4: 1,
        5: 3,
        6: 13,
        **{quota: 14 for quota in range(7, 17)},
    },
    "quota_nested_return_inner": {
        0: 0,
        1: 0,
        **{quota: 1 for quota in range(2, 17)},
    },
    "quota_nested_return_outer": {
        0: 0,
        1: 0,
        2: 0,
        3: 1,
        4: 11,
        **{quota: 1011 for quota in range(5, 17)},
    },
    "quota_recursive_compiled": {
        0: 0,
        1: 0,
        2: 1,
        3: 2,
        4: 2,
        5: 2,
        6: 3,
        7: 4,
        8: 4,
        9: 4,
        10: 5,
        **{quota: 6 for quota in range(11, 17)},
    },
    "quota_change_limit": {
        0: 0,
        1: 0,
        2: 1,
        3: 1,
        4: 11,
        **{quota: 111 for quota in range(5, 17)},
    },
    # Observed on the mod-free vanilla arm. The child's two adds run, its
    # return fail discards the pending +100 fused tail, and the RCON feedback
    # reports "returned 0" for the failed function. Matrix cell: plain nested
    # child outcome = fail (shared with cbx_return_run_fail and cbx_nested_fail).
    "cbx_return_run_fail_child": {
        0: 0,
        1: 0,
        2: 10,
        **{quota: 30 for quota in range(3, 17)},
    },
    # Observed on the mod-free vanilla arm. The child's +10/+20 run and its
    # pending +100 tail is discarded; a failed return run ends the parent
    # frame, so both parent +1000 tail commands are discarded too, and the
    # RCON feedback reports the parent "returned 0". Matrix cell: return run
    # around a failing child with pending fused tails on both frames.
    "cbx_return_run_fail": {
        0: 0,
        1: 0,
        2: 1,
        3: 1,
        4: 11,
        **{quota: 31 for quota in range(5, 17)},
    },
    # Observed on the mod-free vanilla arm. The failing child discards only
    # its own pending +100 tail; the parent's pending +1000 fused tail still
    # runs once through both additions (2031). Matrix cell: plain nested
    # call around a failing child with pending fused tails on both frames.
    "cbx_nested_fail": {
        0: 0,
        1: 0,
        2: 1,
        3: 1,
        4: 11,
        5: 31,
        6: 1031,
        **{quota: 2031 for quota in range(7, 17)},
    },
    # Observed on the mod-free vanilla arm. The child returns 7, so its
    # pending +100 tail is discarded and the unless branch is skipped; the
    # parent's own pending +1000 fused tail still runs once through both
    # additions (2002). Matrix cell: execute unless function around a child
    # returning a value, with a resumed parent continuation.
    "cbx_unless_success": {
        0: 0,
        1: 0,
        2: 1,
        3: 1,
        4: 2,
        5: 1002,
        **{quota: 2002 for quota in range(6, 17)},
    },
    # Observed on the mod-free vanilla arm. `execute store result` around a
    # scoreboard operation stores the operation's new target value (12 for
    # 3*4) and `execute store success` stores 1 for the following +=; the
    # fold is store_result*10000 + store_success*100 + target = 120116.
    "score_op_store_result": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0,
        10: 12, 11: 1200, 12: 1200, 13: 1200, 14: 1201, 15: 120100,
        16: 120116,
    },
    # Observed on the mod-free vanilla arm. An operation whose target
    # selector matches no entity stores 0 through `execute store result`
    # and leaves the objective untouched; the seeded source holder is
    # preserved (fold = store*10 + seed = 7).
    "score_op_empty_target": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0,
        **{quota: 7 for quota in range(11, 17)},
    },
    # Observed on the mod-free vanilla arm. A divide-by-zero operation
    # fails and both callbacks store 0; the target keeps 7 and the
    # following fold reads 7.
    "score_op_store_fail": {
        0: 0, 1: 0, 2: 0, 3: 0, 4: 0, 5: 0, 6: 0, 7: 0, 8: 0, 9: 0, 10: 0,
        11: 0, 12: 0, 13: 0, 14: 0, 15: 0, 16: 7,
    },
}

RECURSIVE_MAX_SCORE = 4
RECURSIVE_COMPILED_MAX_SCORE = 6


class RconClient:
    def __init__(self, host: str, port: int, password: str) -> None:
        self.socket = socket.create_connection((host, port), timeout=5)
        self.socket.settimeout(10)
        self.request_id = 0
        response_id, response_type, _ = self._request(3, password)
        if response_id == -1 or response_type != 2:
            raise RuntimeError("RCON authentication failed")

    def close(self) -> None:
        self.socket.close()

    def command(self, command: str) -> str:
        response_id, response_type, response = self._request(2, command)
        if response_id != self.request_id or response_type != 0:
            raise RuntimeError(
                f"Unexpected RCON command response id={response_id} type={response_type}"
            )
        return response

    def _request(self, packet_type: int, body: str) -> tuple[int, int, str]:
        self.request_id += 1
        packet_id = self.request_id
        encoded = body.encode("utf-8") + b"\0\0"
        payload = struct.pack("<ii", packet_id, packet_type) + encoded
        self.socket.sendall(struct.pack("<i", len(payload)) + payload)

        packet_length = struct.unpack("<i", self._read_exact(4))[0]
        packet = self._read_exact(packet_length)
        response_id, response_type = struct.unpack("<ii", packet[:8])
        response_body = packet[8:-2].decode("utf-8", errors="replace")
        return response_id, response_type, response_body

    def _read_exact(self, length: int) -> bytes:
        chunks = bytearray()
        while len(chunks) < length:
            chunk = self.socket.recv(length - len(chunks))
            if not chunk:
                raise ConnectionError("RCON closed before sending a full packet")
            chunks.extend(chunk)
        return bytes(chunks)


def prepare_server_files() -> Path:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    logs_dir = RUN_DIR / "logs"
    if logs_dir.exists():
        shutil.rmtree(logs_dir)
    debug_dir = RUN_DIR / "debug"
    if debug_dir.exists():
        shutil.rmtree(debug_dir)
    world_dir = RUN_DIR / "probe-world"
    if world_dir.exists():
        shutil.rmtree(world_dir)
    lifecycle_pack_root = world_dir / "datapacks" / LIFECYCLE_PACK
    shutil.copytree(
        ROOT / "tests" / "fixtures" / LIFECYCLE_PACK,
        lifecycle_pack_root,
    )
    shutil.copytree(
        ROOT / "tests" / "fixtures" / PARTNER_LOAD_PACK,
        world_dir / "datapacks" / PARTNER_LOAD_PACK,
    )
    (RUN_DIR / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": RCON_PASSWORD,
        "rcon.port": str(RCON_PORT),
        "broadcast-rcon-to-ops": "false",
        "server-port": str(SERVER_PORT),
        "level-name": "probe-world",
        "online-mode": "false",
        "white-list": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": "4",
        "simulation-distance": "4",
        "sync-chunk-writes": "false",
        "pause-when-empty-seconds": "-1",
    }
    (RUN_DIR / "server.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()),
        encoding="utf-8",
    )
    return lifecycle_pack_root


def prepare_macro_server_files(stack: str) -> Path:
    if stack not in STACK_MODS:
        raise ValueError(f"Unknown Minecraft 26.3 mod stack: {stack}")
    lifecycle_pack_root = prepare_server_files()
    mods_dir = RUN_DIR / "mods"
    if mods_dir.exists():
        shutil.rmtree(mods_dir)
    mod_keys = STACK_MODS[stack]
    if mod_keys:
        mods_dir.mkdir()
        for key in mod_keys:
            filename, expected_hash = MODS[key]
            mod_path = MODS_DIR / filename
            if not mod_path.is_file():
                raise FileNotFoundError(f"Missing pinned {key} jar: {mod_path}")
            with mod_path.open("rb") as mod_file:
                actual_hash = hashlib.file_digest(mod_file, "sha256").hexdigest()
            if actual_hash != expected_hash:
                raise RuntimeError(
                    f"Pinned {key} jar fingerprint mismatch: {actual_hash}"
                )
            shutil.copy2(mod_path, mods_dir / filename)
    return lifecycle_pack_root


def locate_official_server_jar() -> Path:
    cache_roots: list[Path] = []
    configured_gradle_home = os.environ.get("GRADLE_USER_HOME")
    if configured_gradle_home:
        cache_roots.append(Path(configured_gradle_home).expanduser().resolve())
    cache_roots.extend(
        (ROOT / ".gradle-user-home", Path.home() / ".gradle")
    )

    for gradle_home in cache_roots:
        candidate = gradle_home / "caches" / "fabric-loom" / "26.3" / "minecraft-server.jar"
        if candidate.is_file():
            with candidate.open("rb") as server_file:
                digest = hashlib.file_digest(server_file, "sha256").hexdigest()
            if digest != SERVER_JAR_SHA256:
                raise RuntimeError(
                    f"Cached server jar fingerprint mismatch at {candidate}: {digest}"
                )
            return candidate
    raise FileNotFoundError(
        "Official Minecraft 26.3 server jar is not cached. Run the pinned Gradle "
        "build once or set GRADLE_USER_HOME to the cache containing it."
    )


def generate_packet_ids(server_jar: Path) -> PacketIds:
    with tempfile.TemporaryDirectory(prefix="function-compiler-packet-report-") as temp:
        temp_dir = Path(temp)
        report_root = temp_dir / "packet-report"
        report = subprocess.run(
            [
                "java",
                "-DbundlerMainClass=net.minecraft.data.Main",
                "-jar",
                str(server_jar),
                "--reports",
                "--output",
                str(report_root),
            ],
            cwd=temp_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=300,
            check=False,
        )
        packet_report = report_root / "reports" / "packets.json"
        if report.returncode != 0 or not packet_report.is_file():
            raise RuntimeError(
                "Minecraft packet report generation failed: " + report.stdout[-1600:]
            )
        return PacketIds.load(packet_report)


def connect_probe_player(
    packet_ids: PacketIds, client: RconClient, mode: str
) -> PlayerBot:
    last_error: Exception | None = None
    bot: PlayerBot | None = None
    for attempt in range(1, 4):
        candidate = PlayerBot("FCProbe", RCON_HOST, SERVER_PORT, packet_ids)
        try:
            bot = candidate.connect()
            break
        except (ConnectionError, OSError, RuntimeError, TimeoutError) as error:
            candidate.close()
            last_error = error
            if attempt == 3:
                raise RuntimeError(
                    f"{mode} player handshake failed after {attempt} attempts: {error}"
                ) from error
            time.sleep(1)
    if bot is None:
        raise RuntimeError(f"{mode} player handshake failed: {last_error}")
    try:
        for command in ("gamemode creative FCProbe", "tp FCProbe 0 100 0"):
            response = client.command(command)
            if "Unknown" in response or "Could not" in response:
                raise RuntimeError(f"{mode} setup command failed: {command}: {response!r}")
        return bot
    except Exception:
        bot.close()
        raise


def read_score(client: RconClient, holder: str, objective: str) -> int:
    response = client.command(f"scoreboard players get {holder} {objective}")
    match = re.search(r"has (-?\d+)", response)
    if match is None:
        raise RuntimeError(f"Could not read {holder} {objective}: {response!r}")
    return int(match.group(1))


def status_counter(status: str, key: str) -> int:
    match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)", status)
    if match is None:
        raise RuntimeError(f"Probe status omitted {key}: {status!r}")
    return int(match.group(1))


def observe_lifecycle_reload_state(client: RconClient) -> dict[str, object]:
    load_count = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    direct_response = client.command(f"function {LIFECYCLE_PACK}:probe")
    direct_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    tag_response = client.command(f"function #{LIFECYCLE_PACK}:probe")
    tag_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    client.command(f"scoreboard players set #reload_new {LIFECYCLE_OBJECTIVE} 0")
    new_function_response = client.command(
        f"function {LIFECYCLE_PACK}:after_failed_reload"
    )
    new_function_score = read_score(client, "#reload_new", LIFECYCLE_OBJECTIVE)
    return {
        "load_count": load_count,
        "direct_response": direct_response,
        "direct_score": direct_score,
        "tag_response": tag_response,
        "tag_score": tag_score,
        "new_function_response": new_function_response,
        "new_function_score": new_function_score,
    }


def enable_datapacks(client: RconClient, mode: str, names: tuple[str, ...]) -> None:
    enabled = client.command("datapack list enabled")
    available = client.command("datapack list available")
    for name in names:
        if name in enabled:
            continue
        if name not in available:
            raise RuntimeError(
                f"{mode} datapack {name} is not available: {available!r}"
            )
        response = client.command(f"datapack enable file/{name}")
        if "Unknown" in response or "Could not" in response:
            raise RuntimeError(f"{mode} could not enable {name}: {response!r}")


def initialize_lifecycle_pack(
    client: RconClient,
    mode: str,
    extra_packs: tuple[str, ...] = (),
) -> dict[str, int | bool]:
    objective_response = client.command(
        f"scoreboard objectives add {LIFECYCLE_OBJECTIVE} dummy"
    )
    if "Unknown" in objective_response or "Incorrect" in objective_response:
        raise RuntimeError(f"{mode} could not create lifecycle objective: {objective_response!r}")
    enable_datapacks(client, mode, (*extra_packs, LIFECYCLE_PACK))
    client.command(f"scoreboard players set #load {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #tick {LIFECYCLE_OBJECTIVE} 0")
    client.command("reload")

    deadline = time.monotonic() + 30
    load_count: int | None = None
    while time.monotonic() < deadline:
        try:
            load_count = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
        except RuntimeError:
            time.sleep(0.1)
            continue
        if load_count >= 1:
            break
        time.sleep(0.1)
    if load_count != 1:
        raise RuntimeError(
            f"{mode} lifecycle load tag ran {load_count!r} times after initialization"
        )

    tick_before = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    time.sleep(1)
    tick_after = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    if tick_after <= tick_before:
        raise RuntimeError(
            f"{mode} lifecycle tick tag did not advance: {tick_before} -> {tick_after}"
        )
    return {
        "load_count": load_count,
        "tick_before": tick_before,
        "tick_after": tick_after,
        "tick_progressed": True,
    }


def run_lifecycle_functions(
    client: RconClient,
    mode: str,
    server_root: Path = RUN_DIR,
) -> dict[str, object]:
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    client.command("function function_compiler_lifecycle:probe")
    direct_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if direct_score != 1:
        raise RuntimeError(f"{mode} lifecycle direct function score was {direct_score}")

    client.command(f"scoreboard players set #tag {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    client.command("function #function_compiler_lifecycle:probe")
    tag_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if tag_score != 1:
        raise RuntimeError(f"{mode} lifecycle function tag did not invoke its member")

    # HOOK-002: a tag listing the same member twice invokes it once - vanilla
    # collapses duplicate entries, and the wrapper must not create a second
    # artifact for the repeated id. The tag/direct identity diagnostics are
    # still checked by the reload machinery's verify_reload_status.
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    duplicate_response = client.command(
        "function #function_compiler_lifecycle:probe_duplicate"
    )
    duplicate_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if duplicate_score != 1:
        raise RuntimeError(
            f"{mode} duplicate tag entries invoked the member {duplicate_score} "
            f"times; expected exactly 1 (vanilla collapses duplicates)"
        )

    # HOOK-002: a tag referencing a function that does not exist fails to load
    # as a whole, so invoking the tag reports no functions and the member never
    # runs. The load-time failure is in the server log; the command-time
    # observable is the RCON feedback plus an untouched member score.
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    missing_member_response = client.command(
        "function #function_compiler_lifecycle:probe_missing"
    )
    missing_member_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if (
        "Can't find any functions for name "
        "function_compiler_lifecycle:probe_missing" not in missing_member_response
        or missing_member_score != 0
    ):
        raise RuntimeError(
            f"{mode} tag with an absent member behaved "
            f"{missing_member_response!r} / score {missing_member_score}; "
            "expected the vanilla 'Can't find any functions' feedback and no "
            "member execution"
        )

    # HOOK-003: the second datapack's #minecraft:load member runs once per load
    # and records the shared count at its run, which measures its order against
    # the first pack's member (1 = the partner ran after the first pack's load
    # function had already advanced the count) without consuming the count.
    partner_seen_initial = read_score(client, "#partner_seen", LIFECYCLE_OBJECTIVE)
    load_count_initial = read_score(client, "#load", LIFECYCLE_OBJECTIVE)

    # HOOK-004: the second #minecraft:tick member copies the accumulated count
    # after the first tick member runs, so the observer's copy equals the
    # counter in every tick. Two separate score reads race a real tick (a tick
    # landing between them shifts one read), so the ordering fact is taken
    # from a QUIET sample: read counter, observer, counter again, and accept
    # the sample only when the two counter reads are equal (no tick landed
    # inside the triple). The content is deterministic either way - an
    # observer that ran before the counter would read one behind in every
    # quiet sample - so the fact separates the two member orders exactly.
    tick_before = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    tick_after_before = read_score(client, "#tick_after", LIFECYCLE_OBJECTIVE)
    time.sleep(1)
    tick_sample = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    tick_after_sample = read_score(client, "#tick_after", LIFECYCLE_OBJECTIVE)
    if tick_sample <= tick_before:
        raise RuntimeError(
            f"{mode} tick tag did not advance: {tick_before} -> {tick_sample}"
        )
    tick_order_fact: bool | None = None
    for _ in range(10):
        counter_first = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
        observer_middle = read_score(client, "#tick_after", LIFECYCLE_OBJECTIVE)
        counter_second = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
        if counter_first == counter_second:
            tick_order_fact = observer_middle == counter_first
            break
        time.sleep(0.05)
    if tick_order_fact is None:
        raise RuntimeError(
            f"{mode} could not obtain a quiet tick sample in 10 attempts"
        )
    if not tick_order_fact:
        raise RuntimeError(
            f"{mode} tick observer does not copy the counter after the counter "
            "member runs; the intra-tag member order changed"
        )

    def macro_diagnostics() -> dict[str, int]:
        if mode == "mod-free-vanilla":
            return {}
        status = client.command("function_compiler_probe status")
        keys = (
            "score_add_compiled_lifecycle_macro_add",
            "score_add_compiled_lifecycle_macro_pair",
            "score_add_executed_lifecycle_macro_add",
            "score_add_executed_lifecycle_macro_pair",
            "score_add_timed_lifecycle_macro_add",
            "score_add_timed_lifecycle_macro_pair",
        )
        values: dict[str, int] = {}
        for key in keys:
            match = re.search(rf"(?:^|\s){key}=(\d+)", status)
            if match is None:
                raise RuntimeError(f"{mode} macro diagnostics omitted {key}: {status!r}")
            values[key] = int(match.group(1))
        return values

    macro_diagnostics_before = macro_diagnostics()
    macro_amounts = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 1]
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    for amount in macro_amounts:
        client.command(
            "function function_compiler_lifecycle:macro_add "
            f"{{amount:{amount}}}"
        )
    macro_score = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    if macro_score != sum(macro_amounts):
        raise RuntimeError(
            f"{mode} macro tuple sequence scored {macro_score}; "
            f"expected {sum(macro_amounts)}"
        )

    storage_set_first = client.command(
        "data modify storage function_compiler_lifecycle:args arguments "
        "set value {amount:2}"
    )
    storage_call_first = client.command(
        "function function_compiler_lifecycle:macro_add "
        "with storage function_compiler_lifecycle:args arguments"
    )
    storage_score_first = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    storage_set_second = client.command(
        "data modify storage function_compiler_lifecycle:args arguments "
        "set value {amount:7}"
    )
    storage_call_second = client.command(
        "function function_compiler_lifecycle:macro_add "
        "with storage function_compiler_lifecycle:args arguments"
    )
    storage_score_second = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    if (storage_score_first, storage_score_second) != (macro_score + 2, macro_score + 9):
        raise RuntimeError(
            f"{mode} macro storage arguments were stale or wrong: "
            f"scores={storage_score_first}, {storage_score_second}; "
            f"set/call={storage_set_first!r}/{storage_call_first!r}, "
            f"{storage_set_second!r}/{storage_call_second!r}"
        )

    collision_first = {"a": 0, "c": 1}
    collision_second = {"a": 1, "c": 0}
    string_hash = lambda value: sum(
        ord(character) * (31 ** index)
        for index, character in enumerate(reversed(value))
    )
    tuple_hash = lambda values: sum(
        string_hash(key) ^ value for key, value in values.items()
    )
    collision_hashes = [tuple_hash(collision_first), tuple_hash(collision_second)]
    if collision_first == collision_second or collision_hashes != [195, 195]:
        raise RuntimeError(f"Macro collision fixture hashes are invalid: {collision_hashes}")

    client.command(f"scoreboard players set #pair_a {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_c {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_sum {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_calls {LIFECYCLE_OBJECTIVE} 0")

    def call_macro_pair(arguments: dict[str, int]) -> None:
        command_arguments = ",".join(f"{key}:{value}" for key, value in arguments.items())
        client.command(
            "function function_compiler_lifecycle:macro_pair "
            f"{{{command_arguments}}}"
        )

    def read_macro_pair_state() -> dict[str, int]:
        return {
            "a": read_score(client, "#pair_a", LIFECYCLE_OBJECTIVE),
            "c": read_score(client, "#pair_c", LIFECYCLE_OBJECTIVE),
            "sum": read_score(client, "#pair_sum", LIFECYCLE_OBJECTIVE),
            "calls": read_score(client, "#pair_calls", LIFECYCLE_OBJECTIVE),
        }

    call_macro_pair(collision_first)
    collision_first_state = read_macro_pair_state()
    for value in range(10, 20):
        call_macro_pair({"a": value, "c": value + 100})
    after_tuple_churn = read_macro_pair_state()
    call_macro_pair(collision_second)
    collision_second_state = read_macro_pair_state()
    call_macro_pair(collision_first)
    collision_first_reuse_state = read_macro_pair_state()
    expected_pair_states = (
        {"a": 0, "c": 1, "sum": 0, "calls": 1},
        {"a": 19, "c": 119, "sum": 145, "calls": 11},
        {"a": 1, "c": 0, "sum": 146, "calls": 12},
        {"a": 0, "c": 1, "sum": 146, "calls": 13},
    )
    actual_pair_states = (
        collision_first_state,
        after_tuple_churn,
        collision_second_state,
        collision_first_reuse_state,
    )
    if actual_pair_states != expected_pair_states:
        raise RuntimeError(
            f"{mode} colliding macro tuples aliased or went stale: "
            f"{actual_pair_states} != {expected_pair_states}"
        )

    macro_diagnostics_after = macro_diagnostics()
    expected_macro_add_calls = (len(macro_amounts) + 2) * 2
    expected_macro_pair_add_calls = 4 * 13
    macro_score_add_calls = expected_macro_add_calls + expected_macro_pair_add_calls
    if macro_diagnostics_before:
        if mode in {
            "score-add-on", "score-add-timed", "instrument-only", "fused-interpreted",
            "bytecode-emitted", "bytecode-compile-failure",
        }:
            for key in (
                "score_add_compiled_lifecycle_macro_add",
                "score_add_compiled_lifecycle_macro_pair",
            ):
                if macro_diagnostics_after[key] <= macro_diagnostics_before[key]:
                    raise RuntimeError(
                        f"{mode} macro specialization did not compile {key}: "
                        f"{macro_diagnostics_before[key]} -> {macro_diagnostics_after[key]}"
                    )
        if mode in {
            "score-add-on", "score-add-timed", "fused-interpreted",
            "bytecode-emitted", "bytecode-compile-failure",
        }:
            add_delta = (
                macro_diagnostics_after["score_add_executed_lifecycle_macro_add"]
                - macro_diagnostics_before["score_add_executed_lifecycle_macro_add"]
            )
            pair_delta = (
                macro_diagnostics_after["score_add_executed_lifecycle_macro_pair"]
                - macro_diagnostics_before["score_add_executed_lifecycle_macro_pair"]
            )
            if (add_delta, pair_delta) != (
                expected_macro_add_calls,
                expected_macro_pair_add_calls,
            ):
                raise RuntimeError(
                    f"{mode} specialized macro ScoreAdd executions were "
                    f"macro_add={add_delta}, macro_pair={pair_delta}; expected "
                    f"{expected_macro_add_calls}/{expected_macro_pair_add_calls}; diagnostics "
                    f"{macro_diagnostics_before} -> {macro_diagnostics_after}"
                )
        if mode in {"instrument-only", "score-add-timed"}:
            add_delta = (
                macro_diagnostics_after["score_add_timed_lifecycle_macro_add"]
                - macro_diagnostics_before["score_add_timed_lifecycle_macro_add"]
            )
            pair_delta = (
                macro_diagnostics_after["score_add_timed_lifecycle_macro_pair"]
                - macro_diagnostics_before["score_add_timed_lifecycle_macro_pair"]
            )
            if (add_delta, pair_delta) != (
                expected_macro_add_calls,
                expected_macro_pair_add_calls,
            ):
                raise RuntimeError(
                    f"{mode} macro timing calls were macro_add={add_delta}, "
                    f"macro_pair={pair_delta}; expected "
                    f"{expected_macro_add_calls}/{expected_macro_pair_add_calls}"
                )

    macro_score_before_invalid = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    missing_argument_response = client.command(
        "function function_compiler_lifecycle:macro_add {}"
    )
    macro_score_after_missing = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    malformed_argument_response = client.command(
        'function function_compiler_lifecycle:macro_add {amount:"not_a_number"}'
    )
    macro_score_after_malformed = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    if (
        macro_score_after_missing != macro_score_before_invalid
        or macro_score_after_malformed != macro_score_before_invalid
    ):
        raise RuntimeError(
            f"{mode} invalid macro arguments changed scoreboard state: "
            f"before={macro_score_before_invalid}, missing={macro_score_after_missing}, "
            f"malformed={macro_score_after_malformed}"
        )

    def selective_macro_counter() -> int:
        if mode == "mod-free-vanilla":
            return 0
        status = client.command("function_compiler_probe status")
        match = re.search(r"(?:^|\s)selective_macro_arguments_used=(\d+)", status)
        if match is None:
            raise RuntimeError(
                f"{mode} status omitted selective macro count: {status!r}"
            )
        return int(match.group(1))

    selective_before = selective_macro_counter()
    forceload_response = client.command("forceload add 0 0")
    time.sleep(1)
    client.command(
        f"kill @e[type={ACTOR_TYPE},tag=fc_selective_source]"
    )
    client.command(
        f"kill @e[type={ACTOR_TYPE},tag=fc_selective_empty]"
    )
    source_selector = (
        f"@e[type={ACTOR_TYPE},tag=fc_selective_source,limit=1]"
    )
    entity_summon_response = client.command(
        f'summon {ACTOR_TYPE} 0 100 0 '
        '{NoGravity:1b,Invisible:1b,Marker:1b,'
        'Tags:["fc_selective_source"]}'
    )
    entity_presence_response = "No entity was found"
    entity_presence_deadline = time.monotonic() + 2
    while time.monotonic() < entity_presence_deadline:
        entity_presence_response = client.command(
            f"data get entity {source_selector} Tags"
        )
        if "No entity was found" not in entity_presence_response:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(
            f"{mode} summoned macro source was not queryable after two seconds: "
            f"summon={entity_summon_response!r}, "
            f"presence={entity_presence_response!r}"
        )
    frontier = ",".join(
        f"{{x:{index},y:{index % 17},z:{index % 31}}}"
        for index in range(48)
    )
    entity_merge_response = client.command(
        f"data merge entity {source_selector} "
        f"{{data:{{amount:7,a:3,c:4,frontier:[{frontier}]}}}}"
    )
    entity_data_response = client.command(
        f"data get entity {source_selector} data"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    entity_macro_response = client.command(
        "function function_compiler_lifecycle:macro_add "
        f"with entity {source_selector} data"
    )
    entity_macro_score = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)

    client.command(f"scoreboard players set #pair_a {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_c {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_sum {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #pair_calls {LIFECYCLE_OBJECTIVE} 0")
    entity_macro_pair_response = client.command(
        "function function_compiler_lifecycle:macro_pair "
        f"with entity {source_selector} data"
    )
    entity_macro_pair_state = {
        "a": read_score(client, "#pair_a", LIFECYCLE_OBJECTIVE),
        "c": read_score(client, "#pair_c", LIFECYCLE_OBJECTIVE),
        "sum": read_score(client, "#pair_sum", LIFECYCLE_OBJECTIVE),
        "calls": read_score(client, "#pair_calls", LIFECYCLE_OBJECTIVE),
    }
    selective_after_single_and_pair = selective_macro_counter()
    selective_direct_hits = selective_after_single_and_pair - selective_before
    expected_direct_hits = 2 if mode == "selective-macro-arguments" else 0
    if selective_direct_hits != expected_direct_hits:
        raise RuntimeError(
            f"{mode} selected {selective_direct_hits} direct macro calls; "
            f"expected {expected_direct_hits}"
        )

    # A multi-function tag and an ordinary function both keep the vanilla path.
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    grouped_macro_response = client.command(
        "function #function_compiler_lifecycle:entity_macro_group "
        f"with entity {source_selector} data"
    )
    grouped_macro_state = {
        "add": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "pair_a": read_score(client, "#pair_a", LIFECYCLE_OBJECTIVE),
        "pair_c": read_score(client, "#pair_c", LIFECYCLE_OBJECTIVE),
    }
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    plain_function_response = client.command(
        "function function_compiler_lifecycle:probe "
        f"with entity {source_selector} data"
    )
    plain_function_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)

    # Missing fields and a missing data compound must use vanilla error paths.
    client.command(
        f"data modify entity {source_selector} data set value {{unrelated:1}}"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    missing_entity_parameter_response = client.command(
        "function function_compiler_lifecycle:macro_add "
        f"with entity {source_selector} data"
    )
    missing_entity_parameter_score = read_score(
        client, "#macro", LIFECYCLE_OBJECTIVE
    )
    client.command(
        f'summon {ACTOR_TYPE} 0 101 0 '
        '{NoGravity:1b,Invisible:1b,Marker:1b,'
        'Tags:["fc_selective_empty"]}'
    )
    missing_entity_data_response = client.command(
        "function function_compiler_lifecycle:macro_add with entity "
        f"@e[type={ACTOR_TYPE},tag=fc_selective_empty,limit=1] data"
    )
    selective_after_fallbacks = selective_macro_counter()

    # Exercise the same argument path under /debug function and preserve its trace.
    client.command(
        f"data modify entity {source_selector} data set value {{amount:5}}"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    debug_root = server_root / "debug"

    def run_debug_macro_trace(function_name: str, label: str) -> tuple[str, str]:
        trace_files_before = set(debug_root.glob("*")) if debug_root.is_dir() else set()
        trace_mtimes_before = {
            candidate: candidate.stat().st_mtime_ns
            for candidate in trace_files_before
            if candidate.is_file()
        }
        response = client.command(f"debug function {function_name}")
        trace_deadline = time.monotonic() + 10
        trace_path: Path | None = None
        while time.monotonic() < trace_deadline:
            trace_candidates = [
                candidate
                for candidate in debug_root.glob("*")
                if candidate.is_file()
                and candidate.stat().st_size > 0
                and (
                    candidate not in trace_files_before
                    or candidate.stat().st_mtime_ns
                    > trace_mtimes_before.get(candidate, -1)
                )
            ] if debug_root.is_dir() else []
            if trace_candidates:
                trace_path = max(
                    trace_candidates, key=lambda candidate: candidate.stat().st_mtime_ns
                )
                break
            time.sleep(0.1)
        if trace_path is None:
            raise RuntimeError(f"{mode} wrote no {label} debug trace")
        return response, trace_path.read_text(encoding="utf-8")

    debug_macro_response, debug_macro_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:entity_macro_outer", "entity macro"
    )
    debug_macro_score = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    selective_after_debug = selective_macro_counter()

    client.command(
        f"data modify entity {source_selector} data set value "
        "{amount:5,nested:{amount:7}}"
    )
    client.command(
        f"scoreboard players set #nested_macro_before {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    client.command(
        f"scoreboard players set #nested_macro_after {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0")
    selective_before_nested_path = selective_macro_counter()
    nested_path_debug_response, nested_path_debug_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:entity_macro_nested_outer",
        "nested entity macro path",
    )
    nested_path_state = {
        "before": read_score(client, "#nested_macro_before", LIFECYCLE_OBJECTIVE),
        "macro_target": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "after": read_score(client, "#nested_macro_after", LIFECYCLE_OBJECTIVE),
        "macro_continuation": read_score(client, "#macro_reload", LIFECYCLE_OBJECTIVE),
    }
    selective_after_nested_path = selective_macro_counter()
    nested_path_selected_calls = (
        selective_after_nested_path - selective_before_nested_path
    )
    if nested_path_state != {
        "before": 1,
        "macro_target": 7,
        "after": 1,
        "macro_continuation": 1,
    }:
        raise RuntimeError(
            f"{mode} nested entity macro path state was {nested_path_state}"
        )
    # A nested compound-valued entity custom-data path is also now a supported
    # selective source, so the selective path legitimately runs once.
    expected_nested_calls = 1 if mode == "selective-macro-arguments" else 0
    if nested_path_selected_calls != expected_nested_calls:
        raise RuntimeError(
            f"{mode} nested entity macro path selection count was "
            f"{nested_path_selected_calls}; expected {expected_nested_calls}"
        )

    client.command(
        f'data modify entity {source_selector} data set value '
        '{amount:"not_an_integer"}'
    )
    client.command(
        f"scoreboard players set #macro_before_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 23")
    client.command(
        f"scoreboard players set #macro_after_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(
        f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0"
    )
    selective_before_invalid_type = selective_macro_counter()
    invalid_type_debug_response, invalid_type_debug_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:entity_macro_invalid_outer",
        "wrong-typed entity macro",
    )
    invalid_type_state = {
        "before_error": read_score(client, "#macro_before_error", LIFECYCLE_OBJECTIVE),
        "macro_target": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "after_error": read_score(client, "#macro_after_error", LIFECYCLE_OBJECTIVE),
        "macro_continuation": read_score(client, "#macro_reload", LIFECYCLE_OBJECTIVE),
    }
    selective_after_invalid_type = selective_macro_counter()
    invalid_type_selected_calls = (
        selective_after_invalid_type - selective_before_invalid_type
    )
    if invalid_type_state != {
        "before_error": 1,
        "macro_target": 23,
        "after_error": 1,
        "macro_continuation": 0,
    }:
        raise RuntimeError(
            f"{mode} wrong-typed entity macro state was {invalid_type_state}"
        )
    expected_invalid_type_calls = 1 if mode == "selective-macro-arguments" else 0
    if invalid_type_selected_calls != expected_invalid_type_calls:
        raise RuntimeError(
            f"{mode} wrong-typed entity macro selected-path count was "
            f"{invalid_type_selected_calls}; expected {expected_invalid_type_calls}"
        )

    composite_payload = (
        '{nested:{value:7},values:[I;1,2,3],labels:["alpha","beta"]}'
    )
    client.command(
        f"data modify entity {source_selector} data merge value "
        f"{{payload:{composite_payload}}}"
    )
    client.command(
        "data modify storage function_compiler_lifecycle:probe entity_payload "
        "set value {stale:1}"
    )
    selective_before_composite = selective_macro_counter()
    composite_macro_response = client.command(
        "function function_compiler_lifecycle:macro_copy_payload "
        f"with entity {source_selector} data"
    )
    composite_storage_response = client.command(
        "data get storage function_compiler_lifecycle:probe entity_payload"
    )
    composite_value_responses = {
        "nested_value": client.command(
            "data get storage function_compiler_lifecycle:probe "
            "entity_payload.nested.value"
        ),
        "integer_array": [
            client.command(
                "data get storage function_compiler_lifecycle:probe "
                f"entity_payload.values[{index}]"
            )
            for index in range(3)
        ],
        "labels": [
            client.command(
                "data get storage function_compiler_lifecycle:probe "
                f"entity_payload.labels[{index}]"
            )
            for index in range(2)
        ],
    }
    expected_value_suffixes = (
        (
            composite_value_responses["nested_value"],
            r"has the following (?:value|contents):\s+7\s*$",
        ),
        (
            composite_value_responses["integer_array"][0],
            r"has the following (?:value|contents):\s+1\s*$",
        ),
        (
            composite_value_responses["integer_array"][1],
            r"has the following (?:value|contents):\s+2\s*$",
        ),
        (
            composite_value_responses["integer_array"][2],
            r"has the following (?:value|contents):\s+3\s*$",
        ),
        (
            composite_value_responses["labels"][0],
            r'has the following (?:value|contents):\s+"alpha"\s*$',
        ),
        (
            composite_value_responses["labels"][1],
            r'has the following (?:value|contents):\s+"beta"\s*$',
        ),
    )
    if any(
        re.search(pattern, response) is None
        for response, pattern in expected_value_suffixes
    ):
        raise RuntimeError(
            f"{mode} entity compound/list/array macro payload did not match: "
            f"storage={composite_storage_response!r}, values={composite_value_responses!r}"
        )
    selective_after_composite = selective_macro_counter()
    composite_selected_calls = selective_after_composite - selective_before_composite
    expected_composite_calls = 1 if mode == "selective-macro-arguments" else 0
    if composite_selected_calls != expected_composite_calls:
        raise RuntimeError(
            f"{mode} composite entity macro selected-path count was "
            f"{composite_selected_calls}; expected {expected_composite_calls}"
        )

    client.command(
        "data modify storage function_compiler_lifecycle:probe storage_invalid "
        'set value {amount:"not_an_integer"}'
    )
    client.command(
        f"scoreboard players set #storage_macro_before_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 23")
    client.command(
        f"scoreboard players set #storage_macro_after_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(
        f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0"
    )
    selective_before_storage_fallback = selective_macro_counter()
    storage_error_debug_response, storage_error_debug_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:storage_macro_invalid_outer",
        "wrong-typed storage macro",
    )
    storage_error_state = {
        "before_error": read_score(
            client, "#storage_macro_before_error", LIFECYCLE_OBJECTIVE
        ),
        "macro_target": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "after_error": read_score(
            client, "#storage_macro_after_error", LIFECYCLE_OBJECTIVE
        ),
        "macro_continuation": read_score(client, "#macro_reload", LIFECYCLE_OBJECTIVE),
    }
    selective_after_storage_fallback = selective_macro_counter()
    storage_fallback_selected_calls = (
        selective_after_storage_fallback - selective_before_storage_fallback
    )
    if storage_error_state != {
        "before_error": 1,
        "macro_target": 23,
        "after_error": 1,
        "macro_continuation": 0,
    }:
        raise RuntimeError(
            f"{mode} wrong-typed storage macro state was {storage_error_state}"
        )
    # Note: the storage provider is a supported selective-macro source.  For a
    # present (even wrong-typed) top-level argument the prototype therefore
    # genuinely takes the selective path; macro expansion then reproduces the
    # same vanilla error.  Requiring zero here asserted native fallback in a
    # case where the prototype's by-construction behavior is to select.
    expected_storage_selected_calls = (
        1 if mode == "selective-macro-arguments" else 0
    )
    if storage_fallback_selected_calls != expected_storage_selected_calls:
        raise RuntimeError(
            f"{mode} storage macro selected-path count was "
            f"{storage_fallback_selected_calls}; expected "
            f"{expected_storage_selected_calls}"
        )

    client.command("setblock 0 102 0 barrel")
    client.command(
        'data modify block 0 102 0 data set value {amount:"not_an_integer"}'
    )
    client.command(
        f"scoreboard players set #block_macro_before_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 23")
    client.command(
        f"scoreboard players set #block_macro_after_error {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(
        f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0"
    )
    selective_before_block_fallback = selective_macro_counter()
    block_error_debug_response, block_error_debug_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:block_macro_invalid_outer",
        "wrong-typed block macro",
    )
    block_error_state = {
        "before_error": read_score(
            client, "#block_macro_before_error", LIFECYCLE_OBJECTIVE
        ),
        "macro_target": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "after_error": read_score(
            client, "#block_macro_after_error", LIFECYCLE_OBJECTIVE
        ),
        "macro_continuation": read_score(client, "#macro_reload", LIFECYCLE_OBJECTIVE),
    }
    selective_after_block_fallback = selective_macro_counter()
    block_fallback_selected_calls = (
        selective_after_block_fallback - selective_before_block_fallback
    )
    client.command("setblock 0 102 0 air")
    if block_error_state != {
        "before_error": 1,
        "macro_target": 23,
        "after_error": 1,
        "macro_continuation": 0,
    }:
        raise RuntimeError(
            f"{mode} wrong-typed block macro state was {block_error_state}"
        )
    if block_fallback_selected_calls != 0:
        raise RuntimeError(
            f"{mode} block macro entered the selective entity-data path "
            f"{block_fallback_selected_calls} times"
        )

    client.command(
        f"data modify entity {source_selector} data.custom_args set value {{amount:9}}"
    )
    client.command(
        f"scoreboard players set #custom_path_before {LIFECYCLE_OBJECTIVE} 0"
    )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    client.command(
        f"scoreboard players set #custom_path_after {LIFECYCLE_OBJECTIVE} 0"
    )
    selective_before_custom_path = selective_macro_counter()
    custom_path_debug_response, custom_path_debug_trace = run_debug_macro_trace(
        "function_compiler_lifecycle:entity_macro_custom_path_outer",
        "custom entity path macro",
    )
    custom_path_state = {
        "before": read_score(
            client, "#custom_path_before", LIFECYCLE_OBJECTIVE
        ),
        "macro_target": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
        "after": read_score(
            client, "#custom_path_after", LIFECYCLE_OBJECTIVE
        ),
    }
    selective_after_custom_path = selective_macro_counter()
    custom_path_selected_calls = (
        selective_after_custom_path - selective_before_custom_path
    )
    if custom_path_state != {
        "before": 1,
        "macro_target": 9,
        "after": 1,
    }:
        raise RuntimeError(
            f"{mode} custom entity path macro state was {custom_path_state}"
        )
    # Custom entity data paths are now optimized through a controlled
    # nested Compound extraction rather than requiring direct source-root "data".
    if mode == "selective-macro-arguments" and custom_path_selected_calls != 1:
        raise RuntimeError(
            f"{mode} custom entity path selection count was "
            f"{custom_path_selected_calls}; expected 1"
        )
    if mode != "selective-macro-arguments" and custom_path_selected_calls != 0:
        raise RuntimeError(
            f"{mode} custom entity path entered the selective entity-data path "
            f"{custom_path_selected_calls} times"
        )

    client.command(
        f"data modify entity {source_selector} data set value {{amount:1}}"
    )
    entity_macro_quota_scores: dict[int, int] = {}
    for quota in range(17):
        client.command(f"gamerule {LEVEL} {quota}")
        client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
        client.command(
            "function function_compiler_lifecycle:macro_add "
            f"with entity {source_selector} data"
        )
        entity_macro_quota_scores[quota] = read_score(
            client, "#macro", LIFECYCLE_OBJECTIVE
        )
    client.command(f"gamerule {LEVEL} 65536")
    selective_after_quota_sweep = selective_macro_counter()
    client.command(
        f"kill @e[type={ACTOR_TYPE},tag=fc_selective_source]"
    )
    client.command(
        f"kill @e[type={ACTOR_TYPE},tag=fc_selective_empty]"
    )

    # HOOK-003/004: the load and tick tag members' own command traces, taken by
    # direct /debug function invocations, record the per-command delegation the
    # tag paths depend on. Both holders are zeroed first so the traced
    # "(now N)" messages are deterministic and identical across arms; the
    # traced load member restores #load to 1, keeping the reload machinery's
    # later baseline read (one advance per publication) unchanged.
    client.command(f"scoreboard players set #load {LIFECYCLE_OBJECTIVE} 0")
    load_member_trace_response, load_member_trace_text = run_debug_macro_trace(
        "function_compiler_lifecycle:load", "lifecycle load member"
    )
    client.command(f"scoreboard players set #tick {LIFECYCLE_OBJECTIVE} 0")
    tick_member_trace_response, tick_member_trace_text = run_debug_macro_trace(
        "function_compiler_lifecycle:tick", "lifecycle tick member"
    )
    load_member_score = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
    tick_member_score = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    # The load member's trace is deterministic (nothing reloads during the
    # window), but the tick holder also receives +1 from the live
    # #minecraft:tick tag between the zeroing and the read, so the tick
    # count is allowed to be 1 or 2 while the trace text itself - recorded
    # with the holder zeroed - stays the parity artifact.
    if load_member_score != 1 or tick_member_score not in (1, 2):
        raise RuntimeError(
            f"{mode} lifecycle member trace changed state: "
            f"load={load_member_score}, tick={tick_member_score}; "
            "expected load 1 and tick 1 or 2"
        )

    if entity_macro_score != 7:
        raise RuntimeError(
            f"{mode} entity macro score was {entity_macro_score}; expected 7; "
            f"forceload={forceload_response!r}, "
            f"summon={entity_summon_response!r}, merge={entity_merge_response!r}, "
            f"data={entity_data_response!r}, "
            f"function={entity_macro_response!r}"
        )
    if entity_macro_pair_state != {"a": 3, "c": 4, "sum": 3, "calls": 1}:
        raise RuntimeError(
            f"{mode} entity multi-parameter macro state was {entity_macro_pair_state}"
        )
    if grouped_macro_state != {"add": 7, "pair_a": 3, "pair_c": 4}:
        raise RuntimeError(
            f"{mode} multi-function macro tag state was {grouped_macro_state}"
        )
    if plain_function_score != 1:
        raise RuntimeError(
            f"{mode} plain function with entity data scored {plain_function_score}"
        )
    if missing_entity_parameter_score != 0 or debug_macro_score != 5:
        raise RuntimeError(
            f"{mode} entity macro failure/debug state was "
            f"{missing_entity_parameter_score}/{debug_macro_score}"
        )
    if mode == "selective-macro-arguments":
        if selective_after_fallbacks != selective_after_single_and_pair:
            raise RuntimeError(
                "Selective macro prototype intercepted a multi-function, plain, "
                "or missing-argument case"
            )
        if selective_after_debug != selective_after_fallbacks + 1:
            raise RuntimeError(
                "Selective macro prototype did not handle the debug-traced call"
            )

    return {
        "direct_score": direct_score,
        "tag_score": tag_score,
        "lifecycle_tag_edges": {
            "duplicate_entries_invocations": duplicate_score,
            "duplicate_entries_response": duplicate_response,
            "absent_member_response": missing_member_response,
            "absent_member_score": missing_member_score,
        },
        "load_partner_pack": {
            "load_count": load_count_initial,
            "partner_seen": partner_seen_initial,
            "partner_after_first_pack": partner_seen_initial == load_count_initial,
        },
        "tick_member_order": {
            # Parity-stable facts only: the counter advanced across the
            # sample window, and the ordering fact is from the quiet sample
            # (observer copy equals the counter when no tick landed inside
            # the triple read). Timing-variant counts are not recorded.
            "tick_advanced": tick_sample > tick_before,
            "observer_after_counter_in_quiet_sample": tick_order_fact,
        },
        "lifecycle_member_traces": {
            # Only the trace text is recorded: the /debug function response
            # embeds the trace file's own timestamp, which is not comparable
            # across arms (the macro fallback comparisons strip their
            # debug_response for the same reason).
            "load_trace": load_member_trace_text,
            "tick_trace": tick_member_trace_text,
        },
        "macro_amounts": macro_amounts,
        "macro_score": macro_score,
        "macro_storage_scores": [storage_score_first, storage_score_second],
        "macro_hash_collision": {
            "hashes": collision_hashes,
            "states": list(actual_pair_states),
        },
        "macro_specialization": {
            "diagnostics_before": macro_diagnostics_before,
            "diagnostics_after": macro_diagnostics_after,
            "expected_score_add_calls": macro_score_add_calls,
        },
        "macro_invalid_arguments": {
            "score": macro_score_before_invalid,
            "missing_response": missing_argument_response,
            "malformed_response": malformed_argument_response,
            "state_unchanged": True,
        },
        "entity_macro_arguments": {
            "single_parameter_score": entity_macro_score,
            "single_parameter_response": entity_macro_response,
            "multi_parameter_state": entity_macro_pair_state,
            "multi_parameter_response": entity_macro_pair_response,
            "multi_function_state": grouped_macro_state,
            "multi_function_response": grouped_macro_response,
            "plain_function_score": plain_function_score,
            "plain_function_response": plain_function_response,
            "missing_parameter_score": missing_entity_parameter_score,
            "missing_parameter_response": missing_entity_parameter_response,
            "missing_data_response": missing_entity_data_response,
            "debug_score": debug_macro_score,
            "debug_response": debug_macro_response,
            "debug_trace": debug_macro_trace,
            "wrong_typed_data": {
                "state": invalid_type_state,
                "debug_response": invalid_type_debug_response,
                "debug_trace": invalid_type_debug_trace,
                "selected_call_delta": invalid_type_selected_calls,
            },
            "composite_payload": {
                "function_response": composite_macro_response,
                "storage_response": composite_storage_response,
                "value_responses": composite_value_responses,
                "selected_call_delta": composite_selected_calls,
            },
            "wrong_typed_storage_fallback": {
                "state": storage_error_state,
                "debug_response": storage_error_debug_response,
                "debug_trace": storage_error_debug_trace,
                "selected_call_delta": storage_fallback_selected_calls,
            },
            "wrong_typed_block_fallback": {
                "state": block_error_state,
                "debug_response": block_error_debug_response,
                "debug_trace": block_error_debug_trace,
                "selected_call_delta": block_fallback_selected_calls,
            },
            "custom_entity_path_fallback": {
                "state": custom_path_state,
                "debug_response": custom_path_debug_response,
                "debug_trace": custom_path_debug_trace,
                "selected_call_delta": custom_path_selected_calls,
            },
            "nested_entity_path_fallback": {
                "state": nested_path_state,
                "debug_response": nested_path_debug_response,
                "debug_trace": nested_path_debug_trace,
                "selected_call_delta": nested_path_selected_calls,
            },
            "quota_scores": entity_macro_quota_scores,
            "selected_call_counts": {
                "direct": selective_direct_hits,
                "after_fallbacks": selective_after_fallbacks - selective_before,
                "after_debug": selective_after_debug - selective_before,
                "wrong_typed_data": invalid_type_selected_calls,
                "composite_payload": composite_selected_calls,
                "wrong_typed_storage_fallback": storage_fallback_selected_calls,
                "wrong_typed_block_fallback": block_fallback_selected_calls,
                "custom_entity_path_fallback": custom_path_selected_calls,
                "nested_entity_path_fallback": nested_path_selected_calls,
                "after_quota_sweep": selective_after_quota_sweep - selective_before,
                "metrics_enabled": mode == "selective-macro-arguments",
            },
        },
    }


def collect_queue_cost_trace(mode: str) -> list[str]:
    trace_log = RUN_DIR / "logs" / "debug.log"
    if not trace_log.is_file():
        raise RuntimeError(f"{mode} server did not create its debug log: {trace_log}")
    trace = [
        line.split("FC_TRACE ", 1)[1].strip()
        for line in trace_log.read_text(encoding="utf-8", errors="replace").splitlines()
        if "FC_TRACE " in line
    ]
    (REPORT_DIR / f"{mode}.queue-trace.json").write_text(
        json.dumps(trace, indent=2) + "\n",
        encoding="utf-8",
    )
    observed_quotas = {
        int(match.group(1))
        for event in trace
        if (match := re.search(r"event=queue-boundary quota=(\d+)", event))
    }
    # The custom helper command itself consumes one quota unit before
    # ServerFunctionManager.execute enters its queue. Configured limits 0–7
    # therefore expose queue-start quotas 0–6 in this trace.
    expected_queue_quotas = set(range(min(QUOTAS), max(QUOTAS)))
    missing_quotas = expected_queue_quotas - observed_quotas
    if missing_quotas:
        raise RuntimeError(
            f"{mode} runtime trace missed sequence-limit boundaries "
            f"{sorted(missing_quotas)}"
        )
    return trace


def run_debug_trace_fixture(
    client: RconClient,
    mode: str,
    server_root: Path,
    function_id: str,
    expected_score: int,
    expected_command_events: int | None,
) -> dict[str, object]:
    debug_root = server_root / "debug"
    files_before = set(debug_root.glob("*")) if debug_root.is_dir() else set()
    mtimes_before = {
        candidate: candidate.stat().st_mtime_ns
        for candidate in files_before
        if candidate.is_file()
    }
    client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    response = client.command(f"debug function {function_id}")
    if "Unknown" in response or "Could not" in response:
        raise RuntimeError(f"{mode} debug function command failed: {response!r}")
    score = read_score(client, HOLDER, OBJECTIVE)
    if score != expected_score:
        raise RuntimeError(
            f"{mode} debug trace changed {function_id} state: "
            f"{score} != {expected_score}"
        )

    deadline = time.monotonic() + 10
    trace_file: Path | None = None
    while time.monotonic() < deadline:
        candidates = [
            candidate
            for candidate in debug_root.glob("*")
            if candidate.is_file()
            and candidate.stat().st_size > 0
            and (
                candidate not in files_before
                or candidate.stat().st_mtime_ns > mtimes_before.get(candidate, -1)
            )
        ] if debug_root.is_dir() else []
        if candidates:
            trace_file = max(candidates, key=lambda candidate: candidate.stat().st_mtime_ns)
            break
        time.sleep(0.1)
    if trace_file is None:
        raise RuntimeError(f"{mode} did not write a trace file for {function_id}")

    trace_text = trace_file.read_text(encoding="utf-8")
    command_events = sum(
        re.match(r"\s*\[C\]", line) is not None
        for line in trace_text.splitlines()
    )
    if (
        expected_command_events is not None
        and command_events != expected_command_events
    ):
        raise RuntimeError(
            f"{mode} {function_id} trace had {command_events} command events; "
            f"expected {expected_command_events}: {trace_text!r}"
        )
    return {
        "function": function_id,
        "score": score,
        "command_events": command_events,
        "trace": trace_text,
        "response": response,
    }


def run_quota_debug_trace_sweep(
    client: RconClient,
    mode: str,
    server_root: Path,
    fixture: str,
    quota_limits: range = QUOTAS,
) -> list[dict[str, object]]:
    function_id = f"function_compiler_probe:{fixture}"
    traces: list[dict[str, object]] = []
    expected_scores = EXPECTED_SCORES[fixture]
    for quota in quota_limits:
        response = client.command(f"gamerule {LEVEL} {quota}")
        if str(quota) not in response:
            raise RuntimeError(
                f"Could not set {mode} nested-call debug quota to {quota}: {response!r}"
            )
        trace = run_debug_trace_fixture(
            client,
            mode,
            server_root,
            function_id,
            expected_score=expected_scores[quota],
            expected_command_events=None,
        )
        trace["quota"] = quota
        traces.append(trace)

    # Preserve the existing high-quota assumptions for later debug fixtures.
    client.command(f"gamerule {LEVEL} 65536")
    return traces


def persist_debug_traces(mode: str, debug_traces: list[dict[str, object]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    for index, item in enumerate(debug_traces):
        trace = item.get("trace")
        if isinstance(trace, str):
            (REPORT_DIR / f"{mode}.debug-trace-{index:02}.txt").write_text(
                trace,
                encoding="utf-8",
            )


def reload_lifecycle_pack(
    client: RconClient,
    mode: str,
    lifecycle_pack_root: Path,
    reload_cycles: int = 5,
    whole_reload_failure_probe: bool = False,
    concurrent_reload_probe: bool = False,
    callback_metric_probe: bool = False,
) -> dict[str, object]:
    function_root = (
        lifecycle_pack_root
        / "data"
        / LIFECYCLE_PACK
        / "function"
    )
    tag_path = (
        lifecycle_pack_root
        / "data"
        / LIFECYCLE_PACK
        / "tags"
        / "function"
        / "probe.json"
    )
    generations: list[dict[str, object]] = []
    expected_load_count = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
    collect_after_reload = reload_cycles > 5
    first_status = ""
    if mode != "mod-free-vanilla":
        first_status = client.command(
            "function_compiler_probe collect"
            if collect_after_reload
            else "function_compiler_probe status"
        )
    parse_match = re.search(r"probe_function_parses=(\d+)", first_status)
    expected_parse_count = int(parse_match.group(1)) if parse_match is not None else None
    compile_match = re.search(r"score_add_compiled_lifecycle_probe=(\d+)", first_status)
    expected_lifecycle_score_add_compiled = (
        int(compile_match.group(1)) if compile_match is not None else None
    )
    initial_live_bytecode_classes = status_counter(
        first_status, "bytecode_generated_classes_live"
    ) if first_status else 0
    initial_bytecode_classloader = status_counter(
        first_status, "bytecode_classloader_identity"
    ) if first_status else 0
    initial_metaspace_bytes = status_counter(
        first_status, "metaspace_bytes_used"
    ) if first_status else 0
    reload_durations_ms: list[float] = []
    live_class_samples: list[int] = []
    metaspace_samples: list[int] = []
    bytecode_bytes_samples: list[int] = []
    bytecode_classloader_samples: list[int] = []
    score_add_compile_enabled = mode in {
        "score-add-on", "instrument-only", "score-add-timed", "fused-interpreted",
        "bytecode-emitted", "bytecode-compile-failure",
    }
    macro_file = function_root / "macro_add.mcfunction"
    macro_reload_probe_amount = 37
    macro_source_tag = "fc_macro_reload_source"
    macro_source_selector = (
        f"@e[type={ACTOR_TYPE},tag={macro_source_tag},limit=1]"
    )
    client.command("forceload add 0 0")
    client.command(f"kill @e[type={ACTOR_TYPE},tag={macro_source_tag}]")
    macro_source_summon = client.command(
        f'summon {ACTOR_TYPE} 0 100 0 '
        f'{{NoGravity:1b,Invisible:1b,Marker:1b,Tags:["{macro_source_tag}"]}}'
    )
    macro_source_presence = "No entity was found"
    macro_source_deadline = time.monotonic() + 2
    while time.monotonic() < macro_source_deadline:
        macro_source_presence = client.command(
            f"data get entity {macro_source_selector} Tags"
        )
        if "No entity was found" not in macro_source_presence:
            break
        time.sleep(0.05)
    else:
        raise RuntimeError(
            f"{mode} reload macro source was not queryable: "
            f"summon={macro_source_summon!r}, presence={macro_source_presence!r}"
        )
    macro_source_merge = client.command(
        f"data merge entity {macro_source_selector} "
        f"{{data:{{amount:{macro_reload_probe_amount}}}}}"
    )
    if "No entity was found" in macro_source_merge:
        raise RuntimeError(
            f"{mode} could not seed the reload macro source: {macro_source_merge!r}"
        )

    def call_reload_macro() -> str:
        return client.command(
            f"function {LIFECYCLE_PACK}:macro_add "
            f"with entity {macro_source_selector} data"
        )

    def run_macro_generation() -> dict[str, int]:
        client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
        client.command(
            f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0"
        )
        call_reload_macro()
        return {
            "score": read_score(client, "#macro", LIFECYCLE_OBJECTIVE),
            "body_marker": read_score(client, "#macro_reload", LIFECYCLE_OBJECTIVE),
        }

    def selective_macro_argument_calls() -> int | None:
        if mode != "selective-macro-arguments":
            return None
        return status_counter(
            client.command("function_compiler_probe status"),
            "selective_macro_arguments_used",
        )

    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0")
    call_reload_macro()
    macro_score_before_reload = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    macro_generation_before_reload = read_score(
        client, "#macro_reload", LIFECYCLE_OBJECTIVE
    )
    if (macro_score_before_reload, macro_generation_before_reload) != (
        macro_reload_probe_amount,
        1,
    ):
        raise RuntimeError(
            f"{mode} macro reload baseline was "
            f"score={macro_score_before_reload}, marker={macro_generation_before_reload}"
        )
    macro_compiled_before_reload = (
        status_counter(
            client.command("function_compiler_probe status"),
            "score_add_compiled_lifecycle_macro_add",
        )
        if mode != "mod-free-vanilla"
        else 0
    )
    macro_reload_after_reload: dict[str, int] | None = None

    def reload_and_wait(label: str) -> int:
        nonlocal expected_load_count
        started = time.monotonic()
        client.command("reload")
        expected_load_count += 1
        deadline = time.monotonic() + 30
        actual_load_count: int | None = None
        while time.monotonic() < deadline:
            try:
                actual_load_count = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
            except RuntimeError:
                time.sleep(0.1)
                continue
            if actual_load_count >= expected_load_count:
                break
            time.sleep(0.1)
        if actual_load_count != expected_load_count:
            raise RuntimeError(
                f"{mode} load tag count after {label} was {actual_load_count}; "
                f"expected {expected_load_count}"
            )
        reload_durations_ms.append((time.monotonic() - started) * 1000)
        return actual_load_count

    def assert_parse_count_after_reload(
        label: str,
        status: str,
        parse_count_delta: int = 1,
    ) -> None:
        nonlocal expected_parse_count
        if expected_parse_count is None:
            return
        expected_parse_count += parse_count_delta
        match = re.search(r"probe_function_parses=(\d+)", status)
        if match is None or int(match.group(1)) != expected_parse_count:
            raise RuntimeError(
                f"{mode} parse count after {label} was "
                f"{match.group(1) if match else None}; expected {expected_parse_count}"
            )

    def verify_reload_status(
        label: str,
        expected_flags: dict[str, bool],
        score_add_compile_delta: int = 0,
        parse_count_delta: int = 1,
    ) -> str:
        nonlocal expected_lifecycle_score_add_compiled
        if mode == "mod-free-vanilla":
            return ""
        status = client.command(
            "function_compiler_probe collect"
            if collect_after_reload
            else "function_compiler_probe status"
        )
        for key, expected in expected_flags.items():
            if f"{key}={str(expected).lower()}" not in status:
                raise RuntimeError(
                    f"{mode} {label} failed {key}={expected}: {status!r}"
                )
        assert_parse_count_after_reload(label, status, parse_count_delta)
        if collect_after_reload:
            live_classes = status_counter(status, "bytecode_generated_classes_live")
            metaspace_bytes = status_counter(status, "metaspace_bytes_used")
            emitted_bytes = status_counter(status, "bytecode_class_bytes_emitted")
            classloader_identity = status_counter(
                status, "bytecode_classloader_identity"
            )
            live_class_samples.append(live_classes)
            metaspace_samples.append(metaspace_bytes)
            bytecode_bytes_samples.append(emitted_bytes)
            bytecode_classloader_samples.append(classloader_identity)
            if mode == "bytecode-emitted" and (
                live_classes > initial_live_bytecode_classes + 4
            ):
                raise RuntimeError(
                    f"{mode} retained generated classes after reload {label}: "
                    f"live={live_classes}, baseline={initial_live_bytecode_classes}"
                )
            if mode == "bytecode-emitted" and (
                classloader_identity != initial_bytecode_classloader
            ):
                raise RuntimeError(
                    f"{mode} changed its defining classloader after reload {label}: "
                    f"{classloader_identity} != {initial_bytecode_classloader}"
                )
            if mode == "bytecode-emitted" and (
                metaspace_bytes > initial_metaspace_bytes + 16 * 1024 * 1024
            ):
                raise RuntimeError(
                    f"{mode} metaspace grew by more than 16 MiB after reload {label}: "
                    f"{metaspace_bytes} vs baseline {initial_metaspace_bytes}"
                )
        if expected_lifecycle_score_add_compiled is not None:
            expected_lifecycle_score_add_compiled += score_add_compile_delta
            match = re.search(r"score_add_compiled_lifecycle_probe=(\d+)", status)
            if (
                match is None
                or int(match.group(1)) != expected_lifecycle_score_add_compiled
            ):
                raise RuntimeError(
                    f"{mode} {label} ScoreAdd compile count was "
                    f"{match.group(1) if match else None}; expected "
                    f"{expected_lifecycle_score_add_compiled}"
                )
        return status

    for generation in range(1, reload_cycles + 1):
        direct_value = 10 + generation
        function_file = function_root / "probe.mcfunction"
        function_file.write_text(
            f"scoreboard players add #direct {LIFECYCLE_OBJECTIVE} {direct_value}\n",
            encoding="utf-8",
        )
        if generation == 1:
            macro_file.write_text(
                f"$scoreboard players add #macro {LIFECYCLE_OBJECTIVE} $(amount)\n"
                f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 10\n",
                encoding="utf-8",
            )
        tag_target = "probe_v2" if generation % 2 else "probe"
        tag_path.write_text(
            json.dumps(
                {
                    "replace": False,
                    "values": [f"{LIFECYCLE_PACK}:{tag_target}"],
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )

        actual_load_count = reload_and_wait(f"reload generation {generation}")

        if generation == 1:
            client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
            client.command(
                f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0"
            )
            call_reload_macro()
            macro_score_after_reload = read_score(
                client, "#macro", LIFECYCLE_OBJECTIVE
            )
            macro_generation_after_reload = read_score(
                client, "#macro_reload", LIFECYCLE_OBJECTIVE
            )
            if (macro_score_after_reload, macro_generation_after_reload) != (
                macro_reload_probe_amount,
                10,
            ):
                raise RuntimeError(
                    f"{mode} macro used stale expansion after resource reload: "
                    f"score={macro_score_after_reload}, "
                    f"marker={macro_generation_after_reload}"
                )
            macro_compiled_after_reload = (
                status_counter(
                    client.command("function_compiler_probe status"),
                    "score_add_compiled_lifecycle_macro_add",
                )
                if mode != "mod-free-vanilla"
                else 0
            )
            if mode in MACRO_WRAPPER_MODES and (
                macro_compiled_after_reload <= macro_compiled_before_reload
            ):
                raise RuntimeError(
                    f"{mode} did not specialize the reloaded macro expansion: "
                    f"{macro_compiled_before_reload} -> {macro_compiled_after_reload}"
                )
            macro_reload_after_reload = {
                "same_arguments": macro_reload_probe_amount,
                "score_before_reload": macro_score_before_reload,
                "marker_before_reload": macro_generation_before_reload,
                "score_after_reload": macro_score_after_reload,
                "marker_after_reload": macro_generation_after_reload,
                "compiled_before_reload": macro_compiled_before_reload,
                "compiled_after_reload": macro_compiled_after_reload,
            }

        client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
        client.command(f"function {LIFECYCLE_PACK}:probe")
        direct_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
        if direct_score != direct_value:
            raise RuntimeError(
                f"{mode} stale direct function after reload {generation}: "
                f"score={direct_score}, expected={direct_value}"
            )

        tag_holder = "#tag" if tag_target == "probe_v2" else "#direct"
        client.command(f"scoreboard players set {tag_holder} {LIFECYCLE_OBJECTIVE} 0")
        client.command(f"function #{LIFECYCLE_PACK}:probe")
        tag_score = read_score(client, tag_holder, LIFECYCLE_OBJECTIVE)
        expected_tag_score = 100 if tag_target == "probe_v2" else direct_value
        if tag_score != expected_tag_score:
            raise RuntimeError(
                f"{mode} stale function tag after reload {generation}: "
                f"score={tag_score}, expected={expected_tag_score}"
            )

        expected_probe_wrapped = callback_metric_probe or mode in {
            "wrapper-on", "score-add-on", "instrument-only", "score-add-timed",
            "fused-interpreted", "bytecode-emitted", "bytecode-compile-failure",
            "selective-macro-arguments",
        }
        expected_probe_tag = tag_target == "probe"
        expected_v2_tag = tag_target == "probe_v2"
        verify_reload_status(
            f"reload generation {generation}",
            {
                "lifecycle_probe_wrapped": expected_probe_wrapped,
                "lifecycle_probe_v2_wrapped": expected_probe_wrapped,
                "lifecycle_tag_has_probe": expected_probe_tag,
                "lifecycle_tag_same_probe_instance": expected_probe_tag,
                "lifecycle_tag_has_probe_v2": expected_v2_tag,
                "lifecycle_tag_same_probe_v2_instance": expected_v2_tag,
                "lifecycle_macro_is_macro": True,
                "lifecycle_macro_wrapped": callback_metric_probe or mode in MACRO_WRAPPER_MODES,
            },
            score_add_compile_delta=int(score_add_compile_enabled),
        )

        generations.append(
            {
                "generation": generation,
                "load_count": actual_load_count,
                "direct_score": direct_score,
                "tag_score": tag_score,
                "tag_targets_probe_v2": tag_target == "probe_v2",
                "wrapper_enabled": expected_probe_wrapped,
                "tag_identity_matches": mode != "mod-free-vanilla",
                "parse_count": expected_parse_count,
                "reload_duration_ms": reload_durations_ms[-1],
                "bytecode_generated_classes_live": (
                    live_class_samples[-1] if live_class_samples else None
                ),
                "bytecode_class_bytes_emitted": (
                    bytecode_bytes_samples[-1] if bytecode_bytes_samples else None
                ),
                "metaspace_bytes_used": (
                    metaspace_samples[-1] if metaspace_samples else None
                ),
            }
        )

    compiled_after_generations = expected_lifecycle_score_add_compiled
    function_file = function_root / "probe.mcfunction"
    function_file.unlink()
    tag_path.write_text(
        json.dumps(
            {"replace": False, "values": [f"{LIFECYCLE_PACK}:probe_v2"]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    removal_load_count = reload_and_wait("probe removal")
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    missing_function_response = client.command(f"function {LIFECYCLE_PACK}:probe")
    if "unknown function" not in missing_function_response.casefold():
        raise RuntimeError(
            f"{mode} removed function remained callable: {missing_function_response!r}"
        )
    missing_function_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if missing_function_score != 0:
        raise RuntimeError(
            f"{mode} removed function changed score to {missing_function_score}"
        )
    client.command(f"scoreboard players set #tag {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"function #{LIFECYCLE_PACK}:probe")
    removed_tag_score = read_score(client, "#tag", LIFECYCLE_OBJECTIVE)
    if removed_tag_score != 100:
        raise RuntimeError(
            f"{mode} tag retained removed function after reload: {removed_tag_score}"
        )
    wrapper_enabled = callback_metric_probe or mode in {
        "wrapper-on", "score-add-on", "instrument-only", "score-add-timed",
        "fused-interpreted", "bytecode-emitted", "bytecode-compile-failure",
        "selective-macro-arguments",
    }
    verify_reload_status(
        "probe removal",
        {
            "lifecycle_probe_wrapped": False,
            "lifecycle_probe_v2_wrapped": wrapper_enabled,
            "lifecycle_tag_has_probe": False,
            "lifecycle_tag_same_probe_instance": False,
            "lifecycle_tag_has_probe_v2": True,
            "lifecycle_tag_same_probe_v2_instance": True,
            "lifecycle_macro_is_macro": True,
            "lifecycle_macro_wrapped": callback_metric_probe or mode in MACRO_WRAPPER_MODES,
        },
        score_add_compile_delta=0,
    )
    compiled_after_removal = expected_lifecycle_score_add_compiled

    readded_value = 77
    function_file.write_text(
        f"scoreboard players add #direct {LIFECYCLE_OBJECTIVE} {readded_value}\n",
        encoding="utf-8",
    )
    tag_path.write_text(
        json.dumps(
            {"replace": False, "values": [f"{LIFECYCLE_PACK}:probe"]},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    readded_load_count = reload_and_wait("probe re-addition")
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    readded_direct_response = client.command(f"function {LIFECYCLE_PACK}:probe")
    readded_direct_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if readded_direct_score != readded_value:
        raise RuntimeError(
            f"{mode} re-added function score was {readded_direct_score}; "
            f"expected {readded_value}"
        )
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    readded_tag_response = client.command(f"function #{LIFECYCLE_PACK}:probe")
    readded_tag_score = read_score(client, "#direct", LIFECYCLE_OBJECTIVE)
    if readded_tag_score != readded_value:
        raise RuntimeError(
            f"{mode} re-added tag function score was {readded_tag_score}; "
            f"expected {readded_value}"
        )
    verify_reload_status(
        "probe re-addition",
        {
            "lifecycle_probe_wrapped": wrapper_enabled,
            "lifecycle_probe_v2_wrapped": wrapper_enabled,
            "lifecycle_tag_has_probe": True,
            "lifecycle_tag_same_probe_instance": True,
            "lifecycle_tag_has_probe_v2": False,
            "lifecycle_tag_same_probe_v2_instance": False,
            "lifecycle_macro_is_macro": True,
            "lifecycle_macro_wrapped": callback_metric_probe or mode in MACRO_WRAPPER_MODES,
        },
        score_add_compile_delta=int(score_add_compile_enabled),
    )
    compiled_after_readdition = expected_lifecycle_score_add_compiled

    tick_before = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    time.sleep(1)
    tick_after = read_score(client, "#tick", LIFECYCLE_OBJECTIVE)
    if tick_after <= tick_before:
        raise RuntimeError(f"{mode} tick tag stopped after reloads")

    malformed_function_path = function_root / "invalid_parse.mcfunction"
    malformed_function_path.write_text("scoreboard players add\n", encoding="utf-8")
    malformed_load_before = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
    malformed_load_after = reload_and_wait("malformed function parse")
    if malformed_load_after != malformed_load_before + 1:
        raise RuntimeError(
            f"{mode} malformed function parse prevented valid resources from reloading: "
            f"load count {malformed_load_before} -> {malformed_load_after}"
        )

    parse_error_log = lifecycle_pack_root.parents[2] / "logs" / "latest.log"
    parse_error_marker = (
        f"Failed to load function {LIFECYCLE_PACK}:invalid_parse"
    )
    log_deadline = time.monotonic() + 10
    parse_error_logged = False
    while time.monotonic() < log_deadline:
        if parse_error_log.is_file() and parse_error_marker in parse_error_log.read_text(
            encoding="utf-8", errors="replace"
        ):
            parse_error_logged = True
            break
        time.sleep(0.1)
    if not parse_error_logged:
        raise RuntimeError(
            f"{mode} malformed function parse was not reported in "
            f"{parse_error_log}: {parse_error_marker}"
        )

    malformed_function_response = client.command(
        f"function {LIFECYCLE_PACK}:invalid_parse"
    )
    if "unknown function" not in malformed_function_response.casefold():
        raise RuntimeError(
            f"{mode} malformed function remained callable: "
            f"{malformed_function_response!r}"
        )
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"function {LIFECYCLE_PACK}:probe")
    malformed_reload_direct_score = read_score(
        client, "#direct", LIFECYCLE_OBJECTIVE
    )
    if malformed_reload_direct_score != readded_value:
        raise RuntimeError(
            f"{mode} malformed function parse changed valid probe result to "
            f"{malformed_reload_direct_score}; expected {readded_value}"
        )
    client.command(f"scoreboard players set #direct {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"function #{LIFECYCLE_PACK}:probe")
    malformed_reload_tag_score = read_score(
        client, "#direct", LIFECYCLE_OBJECTIVE
    )
    if malformed_reload_tag_score != readded_value:
        raise RuntimeError(
            f"{mode} malformed function parse changed valid tag result to "
            f"{malformed_reload_tag_score}; expected {readded_value}"
        )
    malformed_reload_status = verify_reload_status(
        "malformed function parse",
        {
            "lifecycle_probe_wrapped": wrapper_enabled,
            "lifecycle_probe_v2_wrapped": wrapper_enabled,
            "lifecycle_tag_has_probe": True,
            "lifecycle_tag_same_probe_instance": True,
            "lifecycle_tag_has_probe_v2": False,
            "lifecycle_tag_same_probe_v2_instance": False,
            "lifecycle_macro_is_macro": True,
            "lifecycle_macro_wrapped": callback_metric_probe or mode in MACRO_WRAPPER_MODES,
        },
        score_add_compile_delta=int(score_add_compile_enabled),
    )
    malformed_reload_parse_count = (
        status_counter(malformed_reload_status, "probe_function_parses")
        if malformed_reload_status
        else None
    )

    malformed_macro_path = function_root / "invalid_macro_parse.mcfunction"
    malformed_macro_path.write_text(
        "$scoreboard players add #macro "
        f"{LIFECYCLE_OBJECTIVE} $(amount\n",
        encoding="utf-8",
    )
    malformed_macro_load_before = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
    malformed_macro_load_after = reload_and_wait("malformed macro template parse")
    if malformed_macro_load_after != malformed_macro_load_before + 1:
        raise RuntimeError(
            f"{mode} malformed macro template prevented valid resources from "
            f"reloading: load count {malformed_macro_load_before} -> "
            f"{malformed_macro_load_after}"
        )

    malformed_macro_marker = (
        f"Failed to load function {LIFECYCLE_PACK}:invalid_macro_parse"
    )
    log_deadline = time.monotonic() + 10
    malformed_macro_logged = False
    while time.monotonic() < log_deadline:
        if parse_error_log.is_file() and malformed_macro_marker in parse_error_log.read_text(
            encoding="utf-8", errors="replace"
        ):
            malformed_macro_logged = True
            break
        time.sleep(0.1)
    if not malformed_macro_logged:
        raise RuntimeError(
            f"{mode} malformed macro template parse was not reported in "
            f"{parse_error_log}: {malformed_macro_marker}"
        )

    malformed_macro_response = client.command(
        f"function {LIFECYCLE_PACK}:invalid_macro_parse"
    )
    if "unknown function" not in malformed_macro_response.casefold():
        raise RuntimeError(
            f"{mode} malformed macro function remained callable: "
            f"{malformed_macro_response!r}"
        )
    client.command(f"scoreboard players set #macro {LIFECYCLE_OBJECTIVE} 0")
    client.command(f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 0")
    call_reload_macro()
    malformed_macro_score = read_score(client, "#macro", LIFECYCLE_OBJECTIVE)
    malformed_macro_marker_score = read_score(
        client, "#macro_reload", LIFECYCLE_OBJECTIVE
    )
    if (malformed_macro_score, malformed_macro_marker_score) != (
        macro_reload_probe_amount,
        10,
    ):
        raise RuntimeError(
            f"{mode} malformed macro template changed the valid macro: "
            f"score={malformed_macro_score}, marker={malformed_macro_marker_score}; "
            f"expected score={macro_reload_probe_amount}, marker=10"
        )
    malformed_macro_status = verify_reload_status(
        "malformed macro template parse",
        {
            "lifecycle_probe_wrapped": wrapper_enabled,
            "lifecycle_probe_v2_wrapped": wrapper_enabled,
            "lifecycle_tag_has_probe": True,
            "lifecycle_tag_same_probe_instance": True,
            "lifecycle_tag_has_probe_v2": False,
            "lifecycle_tag_same_probe_v2_instance": False,
            "lifecycle_macro_is_macro": True,
            "lifecycle_macro_wrapped": (
                callback_metric_probe or mode in MACRO_WRAPPER_MODES
            ),
        },
        score_add_compile_delta=int(score_add_compile_enabled),
    )
    malformed_macro_parse_count = (
        status_counter(malformed_macro_status, "probe_function_parses")
        if malformed_macro_status
        else None
    )

    concurrent_reload_publication: dict[str, object] | None = None
    if concurrent_reload_probe:
        server_root = lifecycle_pack_root.parents[2]
        gate_marker = server_root / "resource-reload-concurrent.trigger"
        gate_entered = gate_marker.with_name(gate_marker.name + ".entered")
        gate_release = gate_marker.with_name(gate_marker.name + ".release")
        if mode != "mod-free-vanilla" and not gate_marker.with_name(
            gate_marker.name + ".armed"
        ).is_file():
            raise RuntimeError(f"{mode} concurrent reload listener was not armed")

        new_direct_value = 303
        new_tag_value = 707
        function_file.write_text(
            f"scoreboard players add #direct {LIFECYCLE_OBJECTIVE} {new_direct_value}\n",
            encoding="utf-8",
        )
        macro_file.write_text(
            f"$scoreboard players add #macro {LIFECYCLE_OBJECTIVE} $(amount)\n"
            f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 303\n",
            encoding="utf-8",
        )
        (function_root / "probe_v2.mcfunction").write_text(
            f"scoreboard players add #tag {LIFECYCLE_OBJECTIVE} {new_tag_value}\n",
            encoding="utf-8",
        )
        tag_path.write_text(
            json.dumps(
                {"replace": False, "values": [f"{LIFECYCLE_PACK}:probe_v2"]},
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        load_count_before = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
        started = time.monotonic()

        def run_lifecycle_score(holder: str, function_id: str) -> int:
            client.command(f"scoreboard players set {holder} {LIFECYCLE_OBJECTIVE} 0")
            client.command(f"function {function_id}")
            return read_score(client, holder, LIFECYCLE_OBJECTIVE)

        old_direct_during_prepare = run_lifecycle_score(
            "#direct", f"{LIFECYCLE_PACK}:probe"
        )
        old_v2_during_prepare = run_lifecycle_score(
            "#tag", f"{LIFECYCLE_PACK}:probe_v2"
        )
        old_tag_during_prepare = run_lifecycle_score(
            "#direct", f"#{LIFECYCLE_PACK}:probe"
        )
        selective_calls_before_preparation = selective_macro_argument_calls()
        old_generation = {
            "direct": old_direct_during_prepare,
            "probe_v2": old_v2_during_prepare,
            "tag": old_tag_during_prepare,
            "macro": run_macro_generation(),
        }
        selective_calls_during_preparation = selective_macro_argument_calls()
        if (
            selective_calls_before_preparation is not None
            and selective_calls_during_preparation
            != selective_calls_before_preparation + 1
        ):
            raise RuntimeError(
                f"{mode} did not use the selective argument path during held "
                f"reload preparation: {selective_calls_before_preparation} -> "
                f"{selective_calls_during_preparation}"
            )
        expected_old_generation = {
            "direct": readded_value,
            "probe_v2": 100,
            "tag": readded_value,
            "macro": {"score": macro_reload_probe_amount, "body_marker": 10},
        }
        if old_generation != expected_old_generation:
            raise RuntimeError(
                f"{mode} changed lifecycle data before async reload publication: "
                f"{old_generation!r}; expected {expected_old_generation!r}"
            )
        macro_specializations_before_reload = (
            status_counter(
                client.command("function_compiler_probe status"),
                "score_add_compiled_lifecycle_macro_add",
            )
            if mode != "mod-free-vanilla"
            else 0
        )

        def stage_overlap_generation(
            direct_value: int,
            tag_value: int,
            macro_marker: int,
            tag_target: str,
        ) -> None:
            function_file.write_text(
                f"scoreboard players add #direct {LIFECYCLE_OBJECTIVE} "
                f"{direct_value}\n",
                encoding="utf-8",
            )
            macro_file.write_text(
                f"$scoreboard players add #macro {LIFECYCLE_OBJECTIVE} $(amount)\n"
                f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} "
                f"{macro_marker}\n",
                encoding="utf-8",
            )
            (function_root / "probe_v2.mcfunction").write_text(
                f"scoreboard players add #tag {LIFECYCLE_OBJECTIVE} "
                f"{tag_value}\n",
                encoding="utf-8",
            )
            tag_path.write_text(
                json.dumps(
                    {"replace": False, "values": [f"{LIFECYCLE_PACK}:{tag_target}"]},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

        def snapshot_overlap_generation(tag_target: str) -> dict[str, object]:
            direct = run_lifecycle_score(
                "#direct", f"{LIFECYCLE_PACK}:probe"
            )
            probe_v2 = run_lifecycle_score(
                "#tag", f"{LIFECYCLE_PACK}:probe_v2"
            )
            tag_holder = "#direct" if tag_target == "probe" else "#tag"
            tag_score = run_lifecycle_score(
                tag_holder, f"#{LIFECYCLE_PACK}:probe"
            )
            return {
                "direct": direct,
                "probe_v2": probe_v2,
                "tag": tag_score,
                "macro": run_macro_generation(),
            }

        def wait_for_load_count(target: int, label: str) -> int:
            deadline = time.monotonic() + 30
            actual: int | None = None
            while time.monotonic() < deadline:
                try:
                    actual = read_score(client, "#load", LIFECYCLE_OBJECTIVE)
                except RuntimeError:
                    time.sleep(0.1)
                    continue
                if actual >= target:
                    break
                time.sleep(0.1)
            if actual != target:
                raise RuntimeError(
                    f"{mode} {label} load-tag count was {actual}; expected {target}"
                )
            return actual

        def issue_overlapping_reload(
            result: dict[str, object], thread_name: str, label: str
        ) -> None:
            def issue() -> None:
                reload_client: RconClient | None = None
                try:
                    reload_client = RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
                    result["response"] = reload_client.command("fc_test_reload_async")
                except BaseException as exception:
                    result["error"] = repr(exception)
                finally:
                    if reload_client is not None:
                        reload_client.close()

            thread = threading.Thread(target=issue, name=thread_name, daemon=True)
            thread.start()
            thread.join(timeout=10)
            if thread.is_alive():
                raise RuntimeError(f"{mode} {label} RCON request did not return")
            if "error" in result:
                raise RuntimeError(
                    f"{mode} could not start {label}: {result['error']}"
                )

        def publish_additional_overlap_generation(
            *,
            label: str,
            direct_value: int,
            tag_value: int,
            macro_marker: int,
            tag_target: str,
            score_add_compile_delta: int,
            parse_count_delta: int,
        ) -> dict[str, object]:
            nonlocal expected_load_count
            stage_overlap_generation(
                direct_value, tag_value, macro_marker, tag_target
            )
            reload_result: dict[str, object] = {}
            if mode == "mod-free-vanilla":
                load_count = reload_and_wait(
                    f"vanilla {label} overlapping-reload generation"
                )
                generation = snapshot_overlap_generation(tag_target)
                calls_before = None
                calls_after = None
                status = None
            else:
                issue_overlapping_reload(
                    reload_result,
                    f"{mode}-{label}-overlapping-resource-reload",
                    f"{label} overlapping reload",
                )
                expected_load_count += 1
                load_count = wait_for_load_count(
                    expected_load_count,
                    f"{label} overlapping reload while first is held",
                )
                calls_before = selective_macro_argument_calls()
                generation = snapshot_overlap_generation(tag_target)
                calls_after = selective_macro_argument_calls()
                if calls_before is not None and calls_after != calls_before + 1:
                    raise RuntimeError(
                        f"{mode} did not use the selective argument path after the "
                        f"{label} overlapping reload: {calls_before} -> {calls_after}"
                    )
                status = verify_reload_status(
                    f"{label} overlapping reload while first is held",
                    {
                        "lifecycle_probe_wrapped": wrapper_enabled,
                        "lifecycle_probe_v2_wrapped": wrapper_enabled,
                        "lifecycle_tag_has_probe": tag_target == "probe",
                        "lifecycle_tag_same_probe_instance": tag_target == "probe",
                        "lifecycle_tag_has_probe_v2": tag_target == "probe_v2",
                        "lifecycle_tag_same_probe_v2_instance": (
                            tag_target == "probe_v2"
                        ),
                        "lifecycle_macro_is_macro": True,
                        "lifecycle_macro_wrapped": (
                            callback_metric_probe or mode in MACRO_WRAPPER_MODES
                        ),
                    },
                    score_add_compile_delta=score_add_compile_delta,
                    parse_count_delta=parse_count_delta,
                )

            expected_generation = {
                "direct": direct_value,
                "probe_v2": tag_value,
                "tag": direct_value if tag_target == "probe" else tag_value,
                "macro": {
                    "score": macro_reload_probe_amount,
                    "body_marker": macro_marker,
                },
            }
            if generation != expected_generation:
                raise RuntimeError(
                    f"{mode} {label} overlapping reload published {generation!r}; "
                    f"expected {expected_generation!r}"
                )
            return {
                "load_count": load_count,
                "generation": generation,
                "expected_generation": expected_generation,
                "status": status,
                "selective_calls_before": calls_before,
                "selective_calls_after": calls_after,
                "reload_response": reload_result.get("response"),
            }

        reload_thread_result: dict[str, object] = {}
        overlapping_reload_thread_result: dict[str, object] = {}
        third_overlapping_reload_thread_result: dict[str, object] = {}
        fourth_overlapping_reload_thread_result: dict[str, object] = {}
        fifth_overlapping_reload_thread_result: dict[str, object] = {}
        preparation_gate_entered = False
        overlap_load_count_after_second: int | None = None
        overlap_generation_after_second: dict[str, object] | None = None
        overlap_status_after_second: str | None = None
        overlap_load_count_after_third: int | None = None
        overlap_generation_after_third: dict[str, object] | None = None
        overlap_status_after_third: str | None = None
        overlap_load_count_after_fourth: int | None = None
        overlap_generation_after_fourth: dict[str, object] | None = None
        overlap_status_after_fourth: str | None = None
        overlap_load_count_after_fifth: int | None = None
        overlap_generation_after_fifth: dict[str, object] | None = None
        overlap_status_after_fifth: str | None = None
        selective_calls_before_fifth_generation: int | None = None
        selective_calls_after_fifth_generation: int | None = None
        overlap_load_count_after_sixth: int | None = None
        overlap_generation_after_sixth: dict[str, object] | None = None
        overlap_status_after_sixth: str | None = None
        selective_calls_before_sixth_generation: int | None = None
        selective_calls_after_sixth_generation: int | None = None
        overlap_load_count_after_seventh: int | None = None
        overlap_generation_after_seventh: dict[str, object] | None = None
        overlap_status_after_seventh: str | None = None
        selective_calls_before_seventh_generation: int | None = None
        selective_calls_after_seventh_generation: int | None = None
        if mode == "mod-free-vanilla":
            stage_overlap_generation(404, 808, 404, "probe")
            overlap_load_count_after_second = reload_and_wait(
                "vanilla second overlapping-reload generation"
            )
            overlap_generation_after_second = snapshot_overlap_generation("probe")
            stage_overlap_generation(505, 909, 505, "probe_v2")
            overlap_load_count_after_third = reload_and_wait(
                "vanilla third overlapping-reload generation"
            )
            overlap_generation_after_third = snapshot_overlap_generation("probe_v2")
            stage_overlap_generation(606, 1010, 606, "probe")
            overlap_load_count_after_fourth = reload_and_wait(
                "vanilla fourth overlapping-reload generation"
            )
            overlap_generation_after_fourth = snapshot_overlap_generation("probe")
            stage_overlap_generation(707, 1111, 707, "probe_v2")
            overlap_load_count_after_fifth = reload_and_wait(
                "vanilla fifth overlapping-reload generation"
            )
            overlap_generation_after_fifth = snapshot_overlap_generation("probe_v2")
            sixth_generation = publish_additional_overlap_generation(
                label="sixth",
                direct_value=808,
                tag_value=1212,
                macro_marker=808,
                tag_target="probe",
                score_add_compile_delta=(
                    1 if score_add_compile_enabled else 0
                ),
                parse_count_delta=1,
            )
            overlap_load_count_after_sixth = int(sixth_generation["load_count"])
            overlap_generation_after_sixth = dict(sixth_generation["generation"])
            seventh_generation = publish_additional_overlap_generation(
                label="seventh",
                direct_value=909,
                tag_value=1313,
                macro_marker=909,
                tag_target="probe_v2",
                score_add_compile_delta=(
                    1 if score_add_compile_enabled else 0
                ),
                parse_count_delta=1,
            )
            overlap_load_count_after_seventh = int(seventh_generation["load_count"])
            overlap_generation_after_seventh = dict(seventh_generation["generation"])
            stage_overlap_generation(
                new_direct_value,
                new_tag_value,
                303,
                "probe_v2",
            )
            load_count_after = reload_and_wait(
                "vanilla delayed first overlapping-reload generation"
            )
            reload_thread_result["response"] = (
                "sequential vanilla reference: newer request then delayed request"
            )
        else:
            gate_marker.write_text(
                "pause the next server-data resource preparation",
                encoding="utf-8",
            )

            def issue_reload() -> None:
                reload_client: RconClient | None = None
                try:
                    reload_client = RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
                    reload_thread_result["response"] = reload_client.command(
                        "fc_test_reload_async"
                    )
                except BaseException as exception:
                    reload_thread_result["error"] = repr(exception)
                finally:
                    if reload_client is not None:
                        reload_client.close()

            reload_thread = threading.Thread(
                target=issue_reload,
                name=f"{mode}-concurrent-resource-reload",
                daemon=True,
            )
            reload_thread.start()
            gate_deadline = time.monotonic() + 30
            while time.monotonic() < gate_deadline and not gate_entered.is_file():
                if "error" in reload_thread_result:
                    raise RuntimeError(
                        f"{mode} could not start gated reload: "
                        f"{reload_thread_result['error']}"
                    )
                time.sleep(0.05)
            if not gate_entered.is_file():
                raise RuntimeError(f"{mode} reload did not enter async preparation gate")
            preparation_gate_entered = True

            old_direct_during_prepare = run_lifecycle_score(
                "#direct", f"{LIFECYCLE_PACK}:probe"
            )
            old_v2_during_prepare = run_lifecycle_score(
                "#tag", f"{LIFECYCLE_PACK}:probe_v2"
            )
            old_tag_during_prepare = run_lifecycle_score(
                "#direct", f"#{LIFECYCLE_PACK}:probe"
            )
            old_generation = {
                "direct": old_direct_during_prepare,
                "probe_v2": old_v2_during_prepare,
                "tag": old_tag_during_prepare,
                "macro": run_macro_generation(),
            }
            if old_generation != expected_old_generation:
                raise RuntimeError(
                    f"{mode} changed lifecycle data before async reload publication: "
                    f"{old_generation!r}; expected {expected_old_generation!r}"
                )

            stage_overlap_generation(404, 808, 404, "probe")
            issue_overlapping_reload(
                overlapping_reload_thread_result,
                f"{mode}-overlapping-resource-reload",
                "second overlapping reload",
            )
            expected_load_count += 1
            overlap_load_count_after_second = wait_for_load_count(
                expected_load_count,
                "second overlapping reload while first is held",
            )
            selective_calls_before_second_generation = (
                selective_macro_argument_calls()
            )
            overlap_generation_after_second = snapshot_overlap_generation("probe")
            selective_calls_after_second_generation = selective_macro_argument_calls()
            if (
                selective_calls_before_second_generation is not None
                and selective_calls_after_second_generation
                != selective_calls_before_second_generation + 1
            ):
                raise RuntimeError(
                    f"{mode} did not use the selective argument path after the "
                    "second overlapping reload: "
                    f"{selective_calls_before_second_generation} -> "
                    f"{selective_calls_after_second_generation}"
                )
            expected_overlap_generation = {
                "direct": 404,
                "probe_v2": 808,
                "tag": 404,
                "macro": {"score": macro_reload_probe_amount, "body_marker": 404},
            }
            if overlap_generation_after_second != expected_overlap_generation:
                raise RuntimeError(
                    f"{mode} second overlapping reload published "
                    f"{overlap_generation_after_second!r}; expected "
                    f"{expected_overlap_generation!r}"
                )
            if mode != "mod-free-vanilla":
                overlap_status_after_second = verify_reload_status(
                    "second overlapping reload while first is held",
                    {
                        "lifecycle_probe_wrapped": wrapper_enabled,
                        "lifecycle_probe_v2_wrapped": wrapper_enabled,
                        "lifecycle_tag_has_probe": True,
                        "lifecycle_tag_same_probe_instance": True,
                        "lifecycle_tag_has_probe_v2": False,
                        "lifecycle_tag_same_probe_v2_instance": False,
                        "lifecycle_macro_is_macro": True,
                        "lifecycle_macro_wrapped": (
                            callback_metric_probe or mode in MACRO_WRAPPER_MODES
                        ),
                    },
                    score_add_compile_delta=(
                        2 if score_add_compile_enabled else 0
                    ),
                    parse_count_delta=2,
                )

            stage_overlap_generation(505, 909, 505, "probe_v2")
            issue_overlapping_reload(
                third_overlapping_reload_thread_result,
                f"{mode}-third-overlapping-resource-reload",
                "third overlapping reload",
            )
            expected_load_count += 1
            overlap_load_count_after_third = wait_for_load_count(
                expected_load_count,
                "third overlapping reload while first is held",
            )
            selective_calls_before_third_generation = (
                selective_macro_argument_calls()
            )
            overlap_generation_after_third = snapshot_overlap_generation("probe_v2")
            selective_calls_after_third_generation = selective_macro_argument_calls()
            if (
                selective_calls_before_third_generation is not None
                and selective_calls_after_third_generation
                != selective_calls_before_third_generation + 1
            ):
                raise RuntimeError(
                    f"{mode} did not use the selective argument path after the "
                    "third overlapping reload: "
                    f"{selective_calls_before_third_generation} -> "
                    f"{selective_calls_after_third_generation}"
                )
            expected_third_overlap_generation = {
                "direct": 505,
                "probe_v2": 909,
                "tag": 909,
                "macro": {"score": macro_reload_probe_amount, "body_marker": 505},
            }
            if overlap_generation_after_third != expected_third_overlap_generation:
                raise RuntimeError(
                    f"{mode} third overlapping reload published "
                    f"{overlap_generation_after_third!r}; expected "
                    f"{expected_third_overlap_generation!r}"
                )
            if mode != "mod-free-vanilla":
                overlap_status_after_third = verify_reload_status(
                    "third overlapping reload while first is held",
                    {
                        "lifecycle_probe_wrapped": wrapper_enabled,
                        "lifecycle_probe_v2_wrapped": wrapper_enabled,
                        "lifecycle_tag_has_probe": False,
                        "lifecycle_tag_same_probe_instance": False,
                        "lifecycle_tag_has_probe_v2": True,
                        "lifecycle_tag_same_probe_v2_instance": True,
                        "lifecycle_macro_is_macro": True,
                        "lifecycle_macro_wrapped": (
                            callback_metric_probe or mode in MACRO_WRAPPER_MODES
                        ),
                    },
                    score_add_compile_delta=(
                        1 if score_add_compile_enabled else 0
                    ),
                    parse_count_delta=1,
                )

            stage_overlap_generation(606, 1010, 606, "probe")
            issue_overlapping_reload(
                fourth_overlapping_reload_thread_result,
                f"{mode}-fourth-overlapping-resource-reload",
                "fourth overlapping reload",
            )
            expected_load_count += 1
            overlap_load_count_after_fourth = wait_for_load_count(
                expected_load_count,
                "fourth overlapping reload while first is held",
            )
            selective_calls_before_fourth_generation = (
                selective_macro_argument_calls()
            )
            overlap_generation_after_fourth = snapshot_overlap_generation("probe")
            selective_calls_after_fourth_generation = selective_macro_argument_calls()
            if (
                selective_calls_before_fourth_generation is not None
                and selective_calls_after_fourth_generation
                != selective_calls_before_fourth_generation + 1
            ):
                raise RuntimeError(
                    f"{mode} did not use the selective argument path after the "
                    "fourth overlapping reload: "
                    f"{selective_calls_before_fourth_generation} -> "
                    f"{selective_calls_after_fourth_generation}"
                )
            expected_fourth_overlap_generation = {
                "direct": 606,
                "probe_v2": 1010,
                "tag": 606,
                "macro": {"score": macro_reload_probe_amount, "body_marker": 606},
            }
            if overlap_generation_after_fourth != expected_fourth_overlap_generation:
                raise RuntimeError(
                    f"{mode} fourth overlapping reload published "
                    f"{overlap_generation_after_fourth!r}; expected "
                    f"{expected_fourth_overlap_generation!r}"
                )
            if mode != "mod-free-vanilla":
                overlap_status_after_fourth = verify_reload_status(
                    "fourth overlapping reload while first is held",
                    {
                        "lifecycle_probe_wrapped": wrapper_enabled,
                        "lifecycle_probe_v2_wrapped": wrapper_enabled,
                        "lifecycle_tag_has_probe": True,
                        "lifecycle_tag_same_probe_instance": True,
                        "lifecycle_tag_has_probe_v2": False,
                        "lifecycle_tag_same_probe_v2_instance": False,
                        "lifecycle_macro_is_macro": True,
                        "lifecycle_macro_wrapped": (
                            callback_metric_probe or mode in MACRO_WRAPPER_MODES
                        ),
                    },
                    score_add_compile_delta=(
                        1 if score_add_compile_enabled else 0
                    ),
                    parse_count_delta=1,
                )

            stage_overlap_generation(707, 1111, 707, "probe_v2")
            issue_overlapping_reload(
                fifth_overlapping_reload_thread_result,
                f"{mode}-fifth-overlapping-resource-reload",
                "fifth overlapping reload",
            )
            expected_load_count += 1
            overlap_load_count_after_fifth = wait_for_load_count(
                expected_load_count,
                "fifth overlapping reload while first is held",
            )
            selective_calls_before_fifth_generation = selective_macro_argument_calls()
            overlap_generation_after_fifth = snapshot_overlap_generation("probe_v2")
            selective_calls_after_fifth_generation = selective_macro_argument_calls()
            if (
                selective_calls_before_fifth_generation is not None
                and selective_calls_after_fifth_generation
                != selective_calls_before_fifth_generation + 1
            ):
                raise RuntimeError(
                    f"{mode} did not use the selective argument path after the "
                    "fifth overlapping reload: "
                    f"{selective_calls_before_fifth_generation} -> "
                    f"{selective_calls_after_fifth_generation}"
                )
            expected_fifth_overlap_generation = {
                "direct": 707,
                "probe_v2": 1111,
                "tag": 1111,
                "macro": {"score": macro_reload_probe_amount, "body_marker": 707},
            }
            if overlap_generation_after_fifth != expected_fifth_overlap_generation:
                raise RuntimeError(
                    f"{mode} fifth overlapping reload published "
                    f"{overlap_generation_after_fifth!r}; expected "
                    f"{expected_fifth_overlap_generation!r}"
                )
            if mode != "mod-free-vanilla":
                overlap_status_after_fifth = verify_reload_status(
                    "fifth overlapping reload while first is held",
                    {
                        "lifecycle_probe_wrapped": wrapper_enabled,
                        "lifecycle_probe_v2_wrapped": wrapper_enabled,
                        "lifecycle_tag_has_probe": False,
                        "lifecycle_tag_same_probe_instance": False,
                        "lifecycle_tag_has_probe_v2": True,
                        "lifecycle_tag_same_probe_v2_instance": True,
                        "lifecycle_macro_is_macro": True,
                        "lifecycle_macro_wrapped": (
                            callback_metric_probe or mode in MACRO_WRAPPER_MODES
                        ),
                    },
                    score_add_compile_delta=(
                        1 if score_add_compile_enabled else 0
                    ),
                    parse_count_delta=1,
                )

            sixth_generation = publish_additional_overlap_generation(
                label="sixth",
                direct_value=808,
                tag_value=1212,
                macro_marker=808,
                tag_target="probe",
                score_add_compile_delta=(
                    1 if score_add_compile_enabled else 0
                ),
                parse_count_delta=1,
            )
            overlap_load_count_after_sixth = int(sixth_generation["load_count"])
            overlap_generation_after_sixth = dict(sixth_generation["generation"])
            overlap_status_after_sixth = str(sixth_generation["status"])
            selective_calls_before_sixth_generation = sixth_generation[
                "selective_calls_before"
            ]
            selective_calls_after_sixth_generation = sixth_generation[
                "selective_calls_after"
            ]
            seventh_generation = publish_additional_overlap_generation(
                label="seventh",
                direct_value=909,
                tag_value=1313,
                macro_marker=909,
                tag_target="probe_v2",
                score_add_compile_delta=(
                    1 if score_add_compile_enabled else 0
                ),
                parse_count_delta=1,
            )
            overlap_load_count_after_seventh = int(seventh_generation["load_count"])
            overlap_generation_after_seventh = dict(seventh_generation["generation"])
            overlap_status_after_seventh = str(seventh_generation["status"])
            selective_calls_before_seventh_generation = seventh_generation[
                "selective_calls_before"
            ]
            selective_calls_after_seventh_generation = seventh_generation[
                "selective_calls_after"
            ]

            gate_release.write_text("release preparation\n", encoding="utf-8")
            expected_load_count += 1
            load_count_after = wait_for_load_count(
                expected_load_count,
                "first overlapping reload after its delayed publication",
            )
            reload_thread.join(timeout=10)
            if reload_thread.is_alive():
                raise RuntimeError(
                    f"{mode} reload RCON request did not complete after release"
                )
            if "error" in reload_thread_result:
                raise RuntimeError(
                    f"{mode} gated reload request failed: "
                    f"{reload_thread_result['error']}"
                )
            reload_durations_ms.append((time.monotonic() - started) * 1000)

        partner_seen_after_reloads = read_score(
            client, "#partner_seen", LIFECYCLE_OBJECTIVE
        )
        if partner_seen_after_reloads != load_count_after:
            raise RuntimeError(
                f"{mode} partner load-pack member ran "
                f"{partner_seen_after_reloads} times while #load advanced to "
                f"{load_count_after}; expected one partner run per reload"
            )

        new_direct_after_publish = run_lifecycle_score(
            "#direct", f"{LIFECYCLE_PACK}:probe"
        )
        new_v2_after_publish = run_lifecycle_score(
            "#tag", f"{LIFECYCLE_PACK}:probe_v2"
        )
        new_tag_after_publish = run_lifecycle_score(
            "#tag", f"#{LIFECYCLE_PACK}:probe"
        )
        selective_calls_before_publication_check = selective_macro_argument_calls()
        new_generation = {
            "direct": new_direct_after_publish,
            "probe_v2": new_v2_after_publish,
            "tag": new_tag_after_publish,
            "macro": run_macro_generation(),
        }
        selective_calls_after_publication = selective_macro_argument_calls()
        if (
            selective_calls_before_publication_check is not None
            and selective_calls_after_publication
            != selective_calls_before_publication_check + 1
        ):
            raise RuntimeError(
                f"{mode} did not use the selective argument path after reload "
                f"publication: {selective_calls_before_publication_check} -> "
                f"{selective_calls_after_publication}"
            )
        expected_new_generation = {
            "direct": new_direct_value,
            "probe_v2": new_tag_value,
            "tag": new_tag_value,
            "macro": {"score": macro_reload_probe_amount, "body_marker": 303},
        }
        if new_generation != expected_new_generation:
            raise RuntimeError(
                f"{mode} gated reload published incomplete lifecycle data: "
                f"{new_generation!r}; expected {expected_new_generation!r}"
            )
        concurrent_status = (
            verify_reload_status(
                "concurrent reload publication",
                {
                    "lifecycle_probe_wrapped": wrapper_enabled,
                    "lifecycle_probe_v2_wrapped": wrapper_enabled,
                    "lifecycle_tag_has_probe": False,
                    "lifecycle_tag_same_probe_instance": False,
                    "lifecycle_tag_has_probe_v2": True,
                    "lifecycle_tag_same_probe_v2_instance": True,
                    "lifecycle_macro_is_macro": True,
                    "lifecycle_macro_wrapped": (
                        callback_metric_probe or mode in MACRO_WRAPPER_MODES
                    ),
                },
                score_add_compile_delta=0,
                parse_count_delta=0,
            )
            if mode != "mod-free-vanilla"
            else None
        )
        if mode != "mod-free-vanilla":
            macro_specializations_after_reload = status_counter(
                client.command("function_compiler_probe status"),
                "score_add_compiled_lifecycle_macro_add",
            )
            # The staged macro body has two ScoreAdd-specializable lines (the
            # macro add and the reload-marker set), so every held-overlap
            # publication advances the per-function compile counter twice -
            # the same per-line doubling the DataStore and bossbar counters
            # record, versus one line for the probe/tag functions. Seven
            # publications run here (the held first plus the six that publish
            # while it is held), so a wrapping arm advances by 14. The stale
            # +6 constant predated both the doubling and the seventh request,
            # and this run measures it directly: 16 before, 30 after.
            expected_macro_specializations = (
                macro_specializations_before_reload + 14
                if mode in MACRO_WRAPPER_MODES
                else macro_specializations_before_reload
            )
            if macro_specializations_after_reload != expected_macro_specializations:
                raise RuntimeError(
                    f"{mode} concurrent macro body reload specialization count was "
                    f"{macro_specializations_before_reload} -> "
                    f"{macro_specializations_after_reload}; expected "
                    f"{expected_macro_specializations}"
                )
        else:
            macro_specializations_after_reload = 0
        concurrent_reload_publication = {
            "preparation_gate_entered": preparation_gate_entered,
            "load_count_before": load_count_before,
            "load_count_after": load_count_after,
            "old_generation_during_preparation": old_generation,
            "expected_old_generation": expected_old_generation,
            "new_generation_after_publication": new_generation,
            "expected_new_generation": expected_new_generation,
            "overlap_load_count_after_second": overlap_load_count_after_second,
            "overlap_generation_after_second": overlap_generation_after_second,
            "overlap_status_after_second": overlap_status_after_second,
            "overlap_load_count_after_third": overlap_load_count_after_third,
            "overlap_generation_after_third": overlap_generation_after_third,
            "overlap_status_after_third": overlap_status_after_third,
            "overlap_load_count_after_fourth": overlap_load_count_after_fourth,
            "overlap_generation_after_fourth": overlap_generation_after_fourth,
            "overlap_status_after_fourth": overlap_status_after_fourth,
            "overlap_load_count_after_fifth": overlap_load_count_after_fifth,
            "overlap_generation_after_fifth": overlap_generation_after_fifth,
            "overlap_status_after_fifth": overlap_status_after_fifth,
            "overlap_load_count_after_sixth": overlap_load_count_after_sixth,
            "overlap_generation_after_sixth": overlap_generation_after_sixth,
            "overlap_status_after_sixth": overlap_status_after_sixth,
            "overlap_load_count_after_seventh": overlap_load_count_after_seventh,
            "overlap_generation_after_seventh": (
                overlap_generation_after_seventh
            ),
            "overlap_status_after_seventh": overlap_status_after_seventh,
            "partner_seen_after_reloads": partner_seen_after_reloads,
            "selective_calls_before_second_generation": (
                selective_calls_before_second_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_after_second_generation": (
                selective_calls_after_second_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_before_third_generation": (
                selective_calls_before_third_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_after_third_generation": (
                selective_calls_after_third_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_before_fourth_generation": (
                selective_calls_before_fourth_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_after_fourth_generation": (
                selective_calls_after_fourth_generation
                if mode != "mod-free-vanilla"
                else None
            ),
            "selective_calls_before_fifth_generation": (
                selective_calls_before_fifth_generation
            ),
            "selective_calls_after_fifth_generation": (
                selective_calls_after_fifth_generation
            ),
            "selective_calls_before_sixth_generation": (
                selective_calls_before_sixth_generation
            ),
            "selective_calls_after_sixth_generation": (
                selective_calls_after_sixth_generation
            ),
            "selective_calls_before_seventh_generation": (
                selective_calls_before_seventh_generation
            ),
            "selective_calls_after_seventh_generation": (
                selective_calls_after_seventh_generation
            ),
            "overlapping_reload_response": overlapping_reload_thread_result.get(
                "response"
            ),
            "third_overlapping_reload_response": (
                third_overlapping_reload_thread_result.get("response")
            ),
            "fourth_overlapping_reload_response": (
                fourth_overlapping_reload_thread_result.get("response")
            ),
            "fifth_overlapping_reload_response": (
                fifth_overlapping_reload_thread_result.get("response")
            ),
            "sixth_overlapping_reload_response": (
                sixth_generation.get("reload_response")
            ),
            "seventh_overlapping_reload_response": (
                seventh_generation.get("reload_response")
            ),
            "macro_specializations_before_reload": macro_specializations_before_reload,
            "macro_specializations_after_reload": macro_specializations_after_reload,
            "selective_macro_calls_before_preparation": selective_calls_before_preparation,
            "selective_macro_calls_during_preparation": selective_calls_during_preparation,
            "selective_macro_calls_before_publication_check": (
                selective_calls_before_publication_check
            ),
            "selective_macro_calls_after_publication": selective_calls_after_publication,
            "reload_response": reload_thread_result.get("response"),
            "reload_duration_ms": reload_durations_ms[-1],
            "status_after_publication": concurrent_status,
        }
    whole_reload_failure: dict[str, object] | None = None
    if whole_reload_failure_probe:
        baseline_state = observe_lifecycle_reload_state(client)
        baseline_macro_state = run_macro_generation()
        failure_bytecode_before: dict[str, int] | None = None
        if mode == "bytecode-emitted":
            failure_baseline_status = client.command("function_compiler_probe collect")
            failure_bytecode_before = {
                "live_classes": status_counter(
                    failure_baseline_status, "bytecode_generated_classes_live"
                ),
                "class_bytes_emitted": status_counter(
                    failure_baseline_status, "bytecode_class_bytes_emitted"
                ),
                "classloader_identity": status_counter(
                    failure_baseline_status, "bytecode_classloader_identity"
                ),
                "metaspace_bytes": status_counter(
                    failure_baseline_status, "metaspace_bytes_used"
                ),
            }
        expected_macro_body_marker = 303 if concurrent_reload_probe else 10
        if baseline_macro_state != {
            "score": macro_reload_probe_amount,
            "body_marker": expected_macro_body_marker,
        }:
            raise RuntimeError(
                f"{mode} whole-reload failure macro baseline was "
                f"{baseline_macro_state!r}; expected score "
                f"{macro_reload_probe_amount} and marker {expected_macro_body_marker}"
            )
        expected_baseline_state = {
            "direct_score": 303 if concurrent_reload_probe else readded_value,
            "tag_score": 0 if concurrent_reload_probe else readded_value,
            "new_function_score": 0,
        }
        for key, expected in expected_baseline_state.items():
            if baseline_state[key] != expected:
                raise RuntimeError(
                    f"{mode} whole-reload failure baseline {key} was "
                    f"{baseline_state[key]!r}; expected {expected!r}"
                )
        if mode == "mod-free-vanilla":
            whole_reload_failure = {
                "injected": False,
                "baseline": baseline_state,
                "after": None,
                "macro_baseline": baseline_macro_state,
                "macro_after": None,
            }
        else:
            malformed_function_path.unlink(missing_ok=True)
            function_file.write_text(
                f"scoreboard players add #direct {LIFECYCLE_OBJECTIVE} 88\n",
                encoding="utf-8",
            )
            macro_file.write_text(
                f"$scoreboard players add #macro {LIFECYCLE_OBJECTIVE} $(amount)\n"
                f"scoreboard players set #macro_reload {LIFECYCLE_OBJECTIVE} 909\n",
                encoding="utf-8",
            )
            (function_root / "after_failed_reload.mcfunction").write_text(
                f"scoreboard players add #reload_new {LIFECYCLE_OBJECTIVE} 900\n",
                encoding="utf-8",
            )
            tag_path.write_text(
                json.dumps(
                    {"replace": False, "values": [f"{LIFECYCLE_PACK}:probe_v2"]},
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            server_root = lifecycle_pack_root.parents[2]
            failure_marker = server_root / "resource-reload-failure.trigger"
            failure_armed = failure_marker.with_name(failure_marker.name + ".armed")
            failure_observed = failure_marker.with_name(
                failure_marker.name + ".observed"
            )
            if not failure_armed.is_file():
                raise RuntimeError(
                    f"{mode} whole-reload failure listener was not armed: "
                    f"{failure_armed}"
                )
            failure_marker.write_text("fail next server-data reload\n", encoding="utf-8")
            failed_reload_response = client.command("reload")
            if not failure_observed.is_file():
                raise RuntimeError(
                    f"{mode} whole resource reload did not reach the injected listener"
                )

            failure_log_marker = "FC_RESOURCE_RELOAD_FAILURE_PROBE"
            failure_log = server_root / "logs" / "latest.log"
            log_deadline = time.monotonic() + 10
            failure_logged = False
            while time.monotonic() < log_deadline:
                if failure_log.is_file() and failure_log_marker in failure_log.read_text(
                    encoding="utf-8", errors="replace"
                ):
                    failure_logged = True
                    break
                time.sleep(0.1)
            if not failure_logged:
                raise RuntimeError(
                    f"{mode} whole resource reload exception was not logged in "
                    f"{failure_log}"
                )

            after_state = observe_lifecycle_reload_state(client)
            if after_state != baseline_state:
                raise RuntimeError(
                    f"{mode} failed resource reload published new lifecycle data: "
                    f"before={baseline_state!r}, after={after_state!r}"
                )

            selective_calls_before_failure_check = selective_macro_argument_calls()
            macro_after_failure = run_macro_generation()
            selective_calls_after_failure_check = selective_macro_argument_calls()
            if macro_after_failure != baseline_macro_state:
                raise RuntimeError(
                    f"{mode} failed reload changed the published macro generation: "
                    f"before={baseline_macro_state!r}, after={macro_after_failure!r}"
                )
            if (
                selective_calls_before_failure_check is not None
                and selective_calls_after_failure_check
                != selective_calls_before_failure_check + 1
            ):
                raise RuntimeError(
                    f"{mode} did not use the selective argument path after failed "
                    f"reload: {selective_calls_before_failure_check} -> "
                    f"{selective_calls_after_failure_check}"
                )

            status_after_failure = client.command(
                "function_compiler_probe collect"
                if collect_after_reload or mode == "bytecode-emitted"
                else "function_compiler_probe status"
            )
            for key, expected in {
                "lifecycle_probe_wrapped": wrapper_enabled,
                "lifecycle_tag_has_probe": not concurrent_reload_probe,
                "lifecycle_tag_same_probe_instance": not concurrent_reload_probe,
                "lifecycle_tag_has_probe_v2": concurrent_reload_probe,
                "lifecycle_tag_same_probe_v2_instance": concurrent_reload_probe,
            }.items():
                if f"{key}={str(expected).lower()}" not in status_after_failure:
                    raise RuntimeError(
                        f"{mode} failed resource reload changed {key}: "
                        f"{status_after_failure!r}"
                    )
            failure_bytecode_retention: dict[str, int] | None = None
            if failure_bytecode_before is not None:
                failure_bytecode_after = {
                    "live_classes": status_counter(
                        status_after_failure, "bytecode_generated_classes_live"
                    ),
                    "class_bytes_emitted": status_counter(
                        status_after_failure, "bytecode_class_bytes_emitted"
                    ),
                    "classloader_identity": status_counter(
                        status_after_failure, "bytecode_classloader_identity"
                    ),
                    "metaspace_bytes": status_counter(
                        status_after_failure, "metaspace_bytes_used"
                    ),
                }
                if (
                    failure_bytecode_after["classloader_identity"]
                    != failure_bytecode_before["classloader_identity"]
                ):
                    raise RuntimeError(
                        f"{mode} changed its generated-class classloader after a "
                        "failed reload: "
                        f"{failure_bytecode_before['classloader_identity']} -> "
                        f"{failure_bytecode_after['classloader_identity']}"
                    )
                if failure_bytecode_after["live_classes"] > (
                    failure_bytecode_before["live_classes"] + 4
                ):
                    raise RuntimeError(
                        f"{mode} retained generated classes from the failed reload: "
                        f"{failure_bytecode_before['live_classes']} -> "
                        f"{failure_bytecode_after['live_classes']}"
                    )
                if failure_bytecode_after["metaspace_bytes"] > (
                    failure_bytecode_before["metaspace_bytes"] + 16 * 1024 * 1024
                ):
                    raise RuntimeError(
                        f"{mode} metaspace grew by more than 16 MiB after failed "
                        "reload: "
                        f"{failure_bytecode_before['metaspace_bytes']} -> "
                        f"{failure_bytecode_after['metaspace_bytes']}"
                    )
                failure_bytecode_retention = {
                    "live_classes_before": failure_bytecode_before["live_classes"],
                    "live_classes_after_gc": failure_bytecode_after["live_classes"],
                    "class_bytes_emitted_before": failure_bytecode_before[
                        "class_bytes_emitted"
                    ],
                    "class_bytes_emitted_after": failure_bytecode_after[
                        "class_bytes_emitted"
                    ],
                    "class_bytes_emitted_delta": (
                        failure_bytecode_after["class_bytes_emitted"]
                        - failure_bytecode_before["class_bytes_emitted"]
                    ),
                    "classloader_identity": failure_bytecode_after[
                        "classloader_identity"
                    ],
                    "metaspace_bytes_before": failure_bytecode_before[
                        "metaspace_bytes"
                    ],
                    "metaspace_bytes_after_gc": failure_bytecode_after[
                        "metaspace_bytes"
                    ],
                }
            whole_reload_failure = {
                "injected": True,
                "listener_observed": failure_observed.is_file(),
                "exception_logged": failure_logged,
                "reload_response": failed_reload_response,
                "baseline": baseline_state,
                "after": after_state,
                "macro_baseline": baseline_macro_state,
                "macro_after": macro_after_failure,
                "selective_macro_calls_before_failure_check": (
                    selective_calls_before_failure_check
                ),
                "selective_macro_calls_after_failure_check": (
                    selective_calls_after_failure_check
                ),
                "probe_function_parse_count_after_failure": status_counter(
                    status_after_failure, "probe_function_parses"
                ),
                "score_add_compiled_probe_after_failure": status_counter(
                    status_after_failure, "score_add_compiled_lifecycle_probe"
                ),
                "bytecode_failed_reload_retention": failure_bytecode_retention,
            }
    return {
        "generations": generations,
        "macro_body_reload": macro_reload_after_reload,
        "reload_cycles": reload_cycles,
        "reload_duration_ms": reload_durations_ms,
        "bytecode_class_retention": {
            "baseline_live_classes": initial_live_bytecode_classes,
            "live_classes_after_gc": live_class_samples,
            "max_live_classes_after_gc": max(live_class_samples, default=None),
            "metaspace_bytes_after_gc": metaspace_samples,
            "max_metaspace_bytes_after_gc": max(metaspace_samples, default=None),
            "baseline_metaspace_bytes_after_gc": initial_metaspace_bytes,
            "metaspace_growth_limit_bytes": 16 * 1024 * 1024,
            "emitted_class_bytes_cumulative": bytecode_bytes_samples,
            "classloader_identity": initial_bytecode_classloader,
            "classloader_identity_after_gc": bytecode_classloader_samples,
        },
        "removal_addition": {
            "removed_load_count": removal_load_count,
            "removed_function_response": missing_function_response,
            "removed_function_score": missing_function_score,
            "tag_after_removal_score": removed_tag_score,
            "readded_load_count": readded_load_count,
            "readded_direct_response": readded_direct_response,
            "readded_direct_score": readded_direct_score,
            "readded_tag_response": readded_tag_response,
            "readded_tag_score": readded_tag_score,
            "score_add_compiled_after_generations": compiled_after_generations,
            "score_add_compiled_after_removal": compiled_after_removal,
            "score_add_compiled_after_readdition": compiled_after_readdition,
            "parse_count": expected_parse_count,
        },
        "malformed_function_parse": {
            "load_count_before": malformed_load_before,
            "load_count_after": malformed_load_after,
            "load_count_delta": malformed_load_after - malformed_load_before,
            "parse_error_logged": parse_error_logged,
            "invalid_function_response": malformed_function_response,
            "invalid_function_score": 0,
            "valid_direct_score": malformed_reload_direct_score,
            "valid_tag_score": malformed_reload_tag_score,
            "probe_function_parse_count": malformed_reload_parse_count,
        },
        "malformed_macro_template_parse": {
            "load_count_before": malformed_macro_load_before,
            "load_count_after": malformed_macro_load_after,
            "load_count_delta": malformed_macro_load_after
            - malformed_macro_load_before,
            "parse_error_logged": malformed_macro_logged,
            "invalid_function_response": malformed_macro_response,
            "valid_macro_score": malformed_macro_score,
            "valid_macro_body_marker": malformed_macro_marker_score,
            "probe_function_parse_count": malformed_macro_parse_count,
        },
        "whole_resource_reload_failure": whole_reload_failure,
        "concurrent_reload_publication": concurrent_reload_publication,
        "final_tick_progressed": True,
        "final_status": (
            client.command("function_compiler_probe status")
            if mode != "mod-free-vanilla"
            else None
        ),
    }


def prepare_vanilla_files(server_dir: Path) -> Path:
    server_dir.mkdir(parents=True, exist_ok=True)
    world_dir = server_dir / "probe-world"
    if world_dir.exists():
        shutil.rmtree(world_dir)
    datapack_root = world_dir / "datapacks" / "function_compiler_probe"
    shutil.copytree(ROOT / "src/main/resources/data", datapack_root / "data")
    (datapack_root / "pack.mcmeta").write_text(
        json.dumps(
            {
                "pack": {
                    "description": "Function Compiler 26.3 runtime reference fixture",
                    "min_format": [97, 1],
                    "max_format": [97, 1],
                }
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    lifecycle_pack_root = world_dir / "datapacks" / LIFECYCLE_PACK
    shutil.copytree(
        ROOT / "tests" / "fixtures" / LIFECYCLE_PACK,
        lifecycle_pack_root,
    )
    shutil.copytree(
        ROOT / "tests" / "fixtures" / PARTNER_LOAD_PACK,
        world_dir / "datapacks" / PARTNER_LOAD_PACK,
    )
    (server_dir / "eula.txt").write_text("eula=true\n", encoding="utf-8")
    properties = {
        "enable-rcon": "true",
        "rcon.password": RCON_PASSWORD,
        "rcon.port": str(RCON_PORT),
        "broadcast-rcon-to-ops": "false",
        "server-port": str(SERVER_PORT),
        "level-name": "probe-world",
        "online-mode": "false",
        "white-list": "false",
        "spawn-protection": "0",
        "max-players": "1",
        "view-distance": "4",
        "simulation-distance": "4",
        "sync-chunk-writes": "false",
        "pause-when-empty-seconds": "-1",
    }
    (server_dir / "server.properties").write_text(
        "".join(f"{key}={value}\n" for key, value in properties.items()),
        encoding="utf-8",
    )
    return lifecycle_pack_root


def start_server(
    mode: str,
    log_path: Path,
    whole_reload_failure_probe: bool = False,
    concurrent_reload_probe: bool = False,
    callback_metric_probe: bool = False,
) -> tuple[subprocess.Popen[bytes], object]:
    log_handle = log_path.open("wb")
    environment = os.environ.copy()
    project_cache = ROOT / ".gradle-user-home"
    if "GRADLE_USER_HOME" not in environment and project_cache.is_dir():
        environment["GRADLE_USER_HOME"] = str(project_cache)
    shared_cache = Path.home() / ".gradle" / "caches"
    if "GRADLE_RO_DEP_CACHE" not in environment and shared_cache.is_dir():
        environment["GRADLE_RO_DEP_CACHE"] = str(shared_cache)
    environment.update(
        {
            "FC_WRAPPER_PROBE": "true" if callback_metric_probe or mode in {
                "wrapper-on", "score-add-on", "instrument-only", "score-add-timed",
                "fused-interpreted", "bytecode-emitted", "bytecode-compile-failure",
                "selective-macro-arguments",
            } else "false",
            "FC_SCORE_ADD_PROTOTYPE": "true" if mode in {
                "score-add-on", "score-add-timed", "fused-interpreted",
                "bytecode-emitted", "bytecode-compile-failure",
            } else "false",
            "FC_SCORE_ADD_METRICS": "true" if mode in {
                "score-add-on", "score-add-timed", "fused-interpreted",
                "bytecode-emitted", "bytecode-compile-failure",
            } else "false",
            "FC_FUSED_REGION_PROTOTYPE": "true" if mode == "fused-interpreted" else "false",
            "FC_BYTECODE_REGION_PROTOTYPE": "true" if mode in {
                "bytecode-emitted", "bytecode-compile-failure"
            } else "false",
            "FC_BYTECODE_FORCE_COMPILE_FAILURE": (
                "true" if mode == "bytecode-compile-failure" else "false"
            ),
            "FC_SCORE_ADD_TIMING": "true" if mode in {
                "instrument-only", "score-add-timed"
            } else "false",
            "FC_RUNTIME_TRACE": "true",
            "FC_COMMAND_CALLBACK_METRICS": str(callback_metric_probe).lower(),
            "FC_COMMAND_CALLBACK_METRICS_ALL_QUEUES": "false",
            "FC_SELECTIVE_MACRO_ARGUMENTS": str(
                mode == "selective-macro-arguments"
            ).lower(),
            "FC_SELECTIVE_MACRO_ARGUMENTS_METRICS": str(
                mode == "selective-macro-arguments"
            ).lower(),
        }
    )
    failure_marker = RUN_DIR / "resource-reload-failure.trigger"
    if whole_reload_failure_probe:
        environment["FC_RESOURCE_RELOAD_FAILURE_MARKER"] = str(failure_marker)
    else:
        environment.pop("FC_RESOURCE_RELOAD_FAILURE_MARKER", None)
    concurrent_marker = RUN_DIR / "resource-reload-concurrent.trigger"
    if concurrent_reload_probe:
        environment["FC_CONCURRENT_RELOAD_MARKER"] = str(concurrent_marker)
    else:
        environment.pop("FC_CONCURRENT_RELOAD_MARKER", None)
    gradle_arguments = [
        "--no-daemon",
        f"-Dorg.gradle.jvmargs={RUNTIME_GRADLE_JVM_ARGS}",
        f"-PfcJvmArgs={','.join(RUNTIME_SERVER_JVM_ARGS)}",
        "runServer",
    ]
    if whole_reload_failure_probe:
        gradle_arguments.insert(-1, "-PfcEnableReloadFailureProbe=true")
    if concurrent_reload_probe:
        gradle_arguments.insert(-1, "-PfcEnableConcurrentReloadProbe=true")
    if os.environ.get("FC_GRADLE_OFFLINE", "").casefold() in {"1", "true", "yes"}:
        gradle_arguments.insert(0, "--offline")
    process = subprocess.Popen(
        [str(ROOT / "gradlew"), *gradle_arguments],
        cwd=ROOT,
        env=environment,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def start_vanilla_server(
    server_jar: Path,
    server_dir: Path,
    log_path: Path,
) -> tuple[subprocess.Popen[bytes], object]:
    log_handle = log_path.open("wb")
    process = subprocess.Popen(
        ["java", *RUNTIME_SERVER_JVM_ARGS, "-jar", str(server_jar), "nogui"],
        cwd=server_dir,
        stdout=log_handle,
        stderr=subprocess.STDOUT,
    )
    return process, log_handle


def wait_for_rcon(process: subprocess.Popen[bytes], timeout_seconds: int = 240) -> RconClient:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"Gradle/server exited early with code {process.returncode}")
        try:
            return RconClient(RCON_HOST, RCON_PORT, RCON_PASSWORD)
        except (OSError, ConnectionError, RuntimeError) as error:
            last_error = error
            time.sleep(1)
    raise TimeoutError(f"RCON did not become available: {last_error}")


def prepare_modifier_actors(client: RconClient, mode: str) -> None:
    forceload_response = client.command("forceload add 0 0")
    time.sleep(1)
    client.command(f"kill @e[type={ACTOR_TYPE},tag={ACTOR_TAG}]")
    summon_responses: list[str] = []
    for _ in range(4):
        response = client.command(
            f'summon {ACTOR_TYPE} 0 100 0 '
            f'{{NoGravity:1b,Invisible:1b,Marker:1b,'
            f'Tags:["{ACTOR_TAG}","{ACTOR_POOL_TAG}"]}}'
        )
        summon_responses.append(response)
        if "summoned" not in response.casefold():
            raise RuntimeError(f"{mode} could not summon modifier fixture actor: {response!r}")
    time.sleep(1)

    client.command(f"scoreboard players set #actor_count {OBJECTIVE} 0")
    counting_response = client.command(
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] "
        f"run scoreboard players add #actor_count {OBJECTIVE} 1"
    )
    count_response = client.command(f"scoreboard players get #actor_count {OBJECTIVE}")
    match = re.search(r"has (-?\d+)", count_response)
    if match is None or int(match.group(1)) != 4:
        client.command(f"scoreboard players set #all_armor_stands {OBJECTIVE} 0")
        all_stands_command = client.command(
            f"execute as @e[type={ACTOR_TYPE}] "
            f"run scoreboard players add #all_armor_stands {OBJECTIVE} 1"
        )
        all_stands_response = client.command(
            f"scoreboard players get #all_armor_stands {OBJECTIVE}"
        )
        data_response = client.command(f"data get entity @e[type={ACTOR_TYPE},limit=1]")
        raise RuntimeError(
            f"{mode} modifier fixture has the wrong actor count: "
            f"forceload={forceload_response!r}, summons={summon_responses!r}, "
            f"tag_count_command={counting_response!r}, tag_count={count_response!r}, "
            f"all_count_command={all_stands_command!r}, all_count={all_stands_response!r}, "
            f"sample={data_response!r}"
        )

    client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    modifier_response = client.command(
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] at @s "
        f"run scoreboard players add {HOLDER} {OBJECTIVE} 1"
    )
    modifier_score = client.command(f"scoreboard players get {HOLDER} {OBJECTIVE}")
    modifier_match = re.search(r"has (-?\d+)", modifier_score)
    if modifier_match is None or int(modifier_match.group(1)) != 4:
        raise RuntimeError(
            f"{mode} direct modifier sanity check failed: "
            f"execute={modifier_response!r}, score={modifier_score!r}"
        )
    client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")


def run_direct_function_fixtures(client: RconClient, mode: str) -> dict[str, dict[str, object]]:
    direct_fixtures: dict[str, dict[str, object]] = {}
    for fixture in DIRECT_FIXTURES:
        scores_for_fixture: dict[int, int] = {}
        responses_for_fixture: list[dict[str, object]] = []
        changed_quota_followups: dict[int, dict[str, object]] = {}
        backend_execution_counter = {
            "fused-interpreted": "fused_regions_executed",
            "bytecode-emitted": "bytecode_regions_executed",
        }.get(mode) if fixture == "quota_recursive_compiled" else None
        backend_execution_before = (
            status_counter(
                client.command("function_compiler_probe status"),
                backend_execution_counter,
            )
            if backend_execution_counter is not None
            else None
        )
        quotas = range(0, 17) if fixture in EXTENDED_QUOTA_FIXTURES else QUOTAS
        for quota in quotas:
            game_rule_response = client.command(f"gamerule {LEVEL} {quota}")
            if str(quota) not in game_rule_response:
                raise RuntimeError(
                    f"Could not set {mode} quota to {quota}: {game_rule_response!r}"
                )
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            function_response = client.command(
                f"function function_compiler_probe:{fixture}"
            )
            if not function_response.startswith("Running function "):
                raise RuntimeError(
                    f"{mode} could not invoke {fixture} at quota {quota}: "
                    f"{function_response!r}"
                )
            score_response = client.command(f"scoreboard players get {HOLDER} {OBJECTIVE}")
            match = re.search(r"has (-?\d+)", score_response)
            if match is None:
                raise RuntimeError(
                    f"Could not parse {mode} {fixture} quota {quota} score: "
                    f"{score_response!r}"
                )
            scores_for_fixture[quota] = int(match.group(1))
            responses_for_fixture.append(
                {
                    "quota": quota,
                    "gamerule": game_rule_response,
                    "function": function_response,
                    "score": score_response,
                }
            )
            if fixture == "quota_change_limit" and quota >= 5:
                # The fixture lowers the gamerule to 1 while its original
                # ExecutionContext is still processing queued entries. That
                # active context must keep its captured quota, while a later
                # function invocation must receive a new context with quota 1.
                client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
                followup_response = client.command(
                    "function function_compiler_probe:quota_three"
                )
                if not followup_response.startswith("Running function "):
                    raise RuntimeError(
                        f"{mode} could not invoke quota_three after the active "
                        f"quota change from {quota}: {followup_response!r}"
                    )
                followup_score_response = client.command(
                    f"scoreboard players get {HOLDER} {OBJECTIVE}"
                )
                followup_match = re.search(r"has (-?\d+)", followup_score_response)
                if followup_match is None or int(followup_match.group(1)) != 0:
                    raise RuntimeError(
                        f"{mode} follow-up quota_three did not use the updated "
                        f"quota of 1 after active quota {quota}: "
                        f"{followup_score_response!r}"
                    )
                changed_quota_followups[quota] = {
                    "function": followup_response,
                    "score": followup_score_response,
                    "expected_score": 0,
                    "effective_quota": 1,
                }
        _assert_fixture_high_quota_result(fixture, scores_for_fixture, mode)
        recursive_max_score = {
            "quota_recursive": RECURSIVE_MAX_SCORE,
            "quota_recursive_compiled": RECURSIVE_COMPILED_MAX_SCORE,
        }.get(fixture)
        backend_execution: dict[str, int | str] | None = None
        if recursive_max_score is not None:
            sequence = [
                scores_for_fixture[quota] for quota in sorted(scores_for_fixture)
            ]
            if (
                any(score < 0 or score > recursive_max_score for score in sequence)
                or any(left > right for left, right in zip(sequence, sequence[1:]))
                or sequence[-1] != recursive_max_score
            ):
                raise RuntimeError(
                    f"{mode} recursive function did not terminate cleanly: {scores_for_fixture}"
                )
        if backend_execution_counter is not None:
            backend_execution_after = status_counter(
                client.command("function_compiler_probe status"),
                backend_execution_counter,
            )
            backend_execution_delta = backend_execution_after - int(backend_execution_before)
            if backend_execution_delta < 1:
                raise RuntimeError(
                    f"{mode} recursive fixture did not enter its compiled region: "
                    f"{backend_execution_counter} delta={backend_execution_delta}"
                )
            backend_execution = {
                "counter": backend_execution_counter,
                "before": int(backend_execution_before),
                "after": backend_execution_after,
                "delta": backend_execution_delta,
            }
        direct_fixtures[fixture] = {
            "scores_by_quota": scores_for_fixture,
            "commands": responses_for_fixture,
            "backend_execution": backend_execution,
        }
        if fixture == "quota_change_limit":
            direct_fixtures[fixture]["followups_after_quota_change"] = (
                changed_quota_followups
            )
    return direct_fixtures


def run_scoreboard_semantics(client: RconClient, mode: str) -> dict[str, object]:
    observations: dict[str, object] = {}

    def command(key: str, value: str) -> str:
        response = client.command(value)
        observations[key] = {"command": value, "response": response}
        return response

    def score(key: str, holder: str, objective: str = OBJECTIVE) -> int:
        value = read_score(client, holder, objective)
        observations[key] = {"holder": holder, "objective": objective, "score": value}
        return value

    def missing_score(key: str, holder: str, objective: str = OBJECTIVE) -> str:
        response = command(key, f"scoreboard players get {holder} {objective}")
        if re.search(r"has -?\d+", response):
            raise RuntimeError(
                f"{mode} expected {holder} to have no score in {objective}: {response!r}"
            )
        return response

    command("set_fixture", f"scoreboard players reset #fcprobe {OBJECTIVE}")
    command("set_function", "function function_compiler_probe:score_set_literal")
    if score("set_value", "#fcprobe") != -17:
        raise RuntimeError(f"{mode} literal scoreboard set did not preserve -17")

    command("absent_add_reset", f"scoreboard players reset #fcprobe {OBJECTIVE}")
    command("absent_add_function", "function function_compiler_probe:score_add_literal")
    if score("absent_add_value", "#fcprobe") != 7:
        raise RuntimeError(f"{mode} scoreboard add did not create an absent fake score")

    command("existing_add_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 5")
    command("existing_add_function", "function function_compiler_probe:score_add_literal")
    if score("existing_add_value", "#fcprobe") != 12:
        raise RuntimeError(f"{mode} scoreboard add did not add to an existing fake score")

    # SCORE-011: external mutation/reset to cached scoreboard holder
    command("mutate_external_set", f"scoreboard players set #fcprobe {OBJECTIVE} 100")
    command("mutate_external_function", "function function_compiler_probe:score_add_literal")
    if score("mutate_external_value", "#fcprobe") != 107:
        raise RuntimeError(f"{mode} scoreboard add did not read externally modified score 100")

    command("mutate_external_reset", f"scoreboard players reset #fcprobe {OBJECTIVE}")
    command("mutate_external_reset_function", "function function_compiler_probe:score_add_literal")
    if score("mutate_external_reset_value", "#fcprobe") != 7:
        raise RuntimeError(f"{mode} scoreboard add did not recreate externally reset score")

    command("mutate_external_holder_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 42")
    command("mutate_external_holder_reset", "scoreboard players reset #fcprobe")
    command("mutate_external_holder_function", "function function_compiler_probe:score_add_literal")
    if score("mutate_external_holder_value", "#fcprobe") != 7:
        raise RuntimeError(f"{mode} scoreboard add did not handle full holder reset")

    command("missing_objective_cleanup", "scoreboard objectives remove fc_missing")
    command("missing_objective_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 0")
    command(
        "missing_objective_function",
        "function function_compiler_probe:score_missing_objective",
    )
    if score("missing_objective_followup", "#fcprobe") != 10:
        raise RuntimeError(
            f"{mode} command after a missing-objective error did not execute"
        )
    command("missing_objective_resume_seed", f"scoreboard players set #after_missing {OBJECTIVE} 0")
    command(
        "missing_objective_resume_function",
        "function function_compiler_probe:score_missing_objective_resume",
    )
    if score("missing_objective_resume_value", "#after_missing") != 10:
        raise RuntimeError(
            f"{mode} function did not continue after its missing-objective command"
        )
    direct_missing_objective_response = command(
        "missing_objective_direct_error",
        "scoreboard players add #fcprobe fc_missing 1",
    )
    if not any(token in direct_missing_objective_response.casefold() for token in ("objective", "unknown")):
        raise RuntimeError(
            f"{mode} missing-objective command did not return its error: "
            f"{direct_missing_objective_response!r}"
        )

    command("missing_objective_store_seed", "scoreboard players set #missing_objective_success fc_probe 1")
    command("missing_objective_store_result_seed", "scoreboard players set #missing_objective_result fc_probe 1")
    command("missing_objective_store_followup_seed", "scoreboard players set #after_missing_objective fc_probe 0")
    command(
        "missing_objective_store_function",
        "function function_compiler_probe:score_missing_objective_store",
    )
    missing_objective_store_success = score(
        "missing_objective_store_success", "#missing_objective_success"
    )
    missing_objective_store_result = score(
        "missing_objective_store_result", "#missing_objective_result"
    )
    missing_objective_followup = score(
        "missing_objective_store_followup", "#after_missing_objective"
    )
    if (
        missing_objective_store_success,
        missing_objective_store_result,
        missing_objective_followup,
    ) != (0, 0, 10):
        raise RuntimeError(
            f"{mode} stored missing-objective failure outcomes were "
            f"success={missing_objective_store_success}, result={missing_objective_store_result}, "
            f"followup={missing_objective_followup}; expected 0, 0, 10"
        )

    command("selector_function", "function function_compiler_probe:score_selector_operands")
    selector_total = score("selector_sum", "#actor_sum")
    command("selector_count_seed", f"scoreboard players set #actor_count {OBJECTIVE} 0")
    command(
        "selector_count_command",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] "
        f"run scoreboard players add #actor_count {OBJECTIVE} 1",
    )
    selector_count = score("selector_count", "#actor_count")
    if selector_count != 4 or selector_total != 20:
        raise RuntimeError(
            f"{mode} selector score operands produced count={selector_count}, sum={selector_total}"
        )

    command(
        "selector_operation_target_seed",
        f"scoreboard players set #selector_operation_target {OBJECTIVE} 10",
    )
    command(
        "selector_operation_followup_seed",
        f"scoreboard players set #selector_operation_followup {OBJECTIVE} 0",
    )
    command(
        "selector_operation_cardinality_function",
        "function function_compiler_probe:score_selector_operation_cardinality",
    )
    selector_operation_target = score(
        "selector_operation_target", "#selector_operation_target"
    )
    selector_operation_followup = score(
        "selector_operation_followup", "#selector_operation_followup"
    )
    expected_selector_operation_target = 10 + selector_total
    if (selector_operation_target, selector_operation_followup) != (
        expected_selector_operation_target,
        7,
    ):
        raise RuntimeError(
            f"{mode} selector operation cardinality produced target/follow-up state "
            f"{selector_operation_target}/{selector_operation_followup}; expected "
            f"{expected_selector_operation_target}/7"
        )

    # SM-10 / SM-13 / SO-07 / SM-12, the selector-shape rows that the compiler
    # declines and must therefore fall back on exactly. Each check invokes a
    # datapack function that performs the mutation and folds the per-entity
    # effect into one fake holder, so the Fabric arms execute it through the
    # compiled path while vanilla runs it directly, and the folded sum is only
    # reachable if the fallback fans out exactly as vanilla does.
    actor_selector = f"@e[type={ACTOR_TYPE},tag={ACTOR_TAG}]"

    command(
        "selector_mutation_reset",
        f"scoreboard players reset {actor_selector} {OBJECTIVE}",
    )
    command(
        "selector_mutation_function",
        "function function_compiler_probe:score_selector_mutation",
    )
    mutation_fanout_sum = score("selector_mutation_sum", "#mutation_sum")
    if mutation_fanout_sum != 20:
        raise RuntimeError(
            f"{mode} multi-entity mutation did not fan out as vanilla does: "
            f"sum={mutation_fanout_sum}; expected 20 (four seeded actors lose 3 "
            f"across the whole selector, then two of them lose 4 more)"
        )

    command("selector_store_function", "function function_compiler_probe:score_selector_store")
    store_fanout_sum = score("selector_store_sum", "#store_sum")
    if store_fanout_sum != 20:
        raise RuntimeError(
            f"{mode} execute store with a selector target did not fan out as "
            f"vanilla does: sum={store_fanout_sum}; expected 20 (the store writes "
            f"the result 5 into each of four actors, creating each score)"
        )

    command(
        "selector_operation_function",
        "function function_compiler_probe:score_selector_operation",
    )
    operation_fanout_sum = score("selector_operation_sum", "#operation_sum")
    if operation_fanout_sum != 5636:
        raise RuntimeError(
            f"{mode} scoreboard operation with a selector target did not fan out "
            f"as vanilla does: sum={operation_fanout_sum}; expected 5636 "
            f"(4*14=56 for the added fan-out, then 4*9=36 for the creation onto "
            f"absent targets, folded one place apart)"
        )

    command(
        "modifier_dispatch_function",
        "function function_compiler_probe:score_modifier_dispatch",
    )
    modifier_dispatch_sum = score("modifier_dispatch_sum", "#modifier_sum")
    if modifier_dispatch_sum != 60020:
        raise RuntimeError(
            f"{mode} mutation in a modifier chain did not dispatch per actor: "
            f"sum={modifier_dispatch_sum}; expected 60020 (a per-actor condition "
            f"counts 2 of 4 actors, an `at @s` chain adds 100 each, and the "
            f"negated condition counts the other 2)"
        )

    command("wildcard_seed_one", f"scoreboard players set #wild_one {OBJECTIVE} 11")
    command("wildcard_seed_two", f"scoreboard players set #wild_two {OBJECTIVE} -3")
    command("wildcard_other_objective", "scoreboard objectives add fc_other dummy")
    command("wildcard_other_seed", "scoreboard players set #wild_one fc_other 19")
    command("wildcard_function", "function function_compiler_probe:score_reset_wildcard")
    missing_score("wildcard_one_reset", "#wild_one")
    missing_score("wildcard_two_reset", "#wild_two")
    if score("wildcard_other_objective_preserved", "#wild_one", "fc_other") != 19:
        raise RuntimeError(f"{mode} wildcard reset crossed objective boundaries")

    command("operation_wildcard_target_objective_cleanup", "scoreboard objectives remove fc_op_target")
    command("operation_wildcard_source_objective_cleanup", "scoreboard objectives remove fc_op_source")
    command("operation_wildcard_target_objective_add", "scoreboard objectives add fc_op_target dummy")
    command("operation_wildcard_source_objective_add", "scoreboard objectives add fc_op_source dummy")
    command("operation_wildcard_target_seed_a", "scoreboard players set #op_target_a fc_op_target 3")
    command("operation_wildcard_target_seed_b", "scoreboard players set #op_target_b fc_op_target 5")
    command("operation_wildcard_source_seed", "scoreboard players set #op_delta fc_op_source 7")
    command(
        "operation_wildcard_target_apply",
        "scoreboard players operation * fc_op_target += #op_delta fc_op_source",
    )
    wildcard_target_a = score("operation_wildcard_target_a", "#op_target_a", "fc_op_target")
    wildcard_target_b = score("operation_wildcard_target_b", "#op_target_b", "fc_op_target")
    if (wildcard_target_a, wildcard_target_b) != (10, 12):
        raise RuntimeError(
            f"{mode} wildcard operation targets became {wildcard_target_a}/{wildcard_target_b}; "
            "expected 10/12"
        )
    wildcard_target_created = score(
        "operation_wildcard_created_unseeded_target", "#op_delta", "fc_op_target"
    )
    if wildcard_target_created != 7:
        raise RuntimeError(
            f"{mode} wildcard operation created #op_delta at {wildcard_target_created}; expected 7"
        )

    operation_family_cases = (
        ("assign", "=", 3, 3),
        ("add", "+=", 10, 3),
        ("subtract", "-=", 4, 3),
        ("multiply", "*=", 21, 3),
        ("divide", "/=", 2, 3),
        ("remainder", "%=", 1, 3),
        ("minimum", "<", 3, 3),
        ("maximum", ">", 7, 3),
        ("swap", "><", 3, 7),
    )
    for name, operation, expected_target, expected_source in operation_family_cases:
        command(
            f"operation_family_{name}_target_seed",
            f"scoreboard players set #operation_family_target {OBJECTIVE} 7",
        )
        command(
            f"operation_family_{name}_source_seed",
            f"scoreboard players set #operation_family_source {OBJECTIVE} 3",
        )
        command(
            f"operation_family_{name}_apply",
            f"scoreboard players operation #operation_family_target {OBJECTIVE} "
            f"{operation} #operation_family_source {OBJECTIVE}",
        )
        actual_target = score(
            f"operation_family_{name}_target", "#operation_family_target"
        )
        actual_source = score(
            f"operation_family_{name}_source", "#operation_family_source"
        )
        if (actual_target, actual_source) != (expected_target, expected_source):
            raise RuntimeError(
                f"{mode} scoreboard operation {operation} produced "
                f"target/source {actual_target}/{actual_source}; expected "
                f"{expected_target}/{expected_source}"
            )

    for name, operation in (("divide_zero", "/="), ("remainder_zero", "%=")):
        command(
            f"operation_{name}_target_seed",
            f"scoreboard players set #operation_zero_target {OBJECTIVE} 7",
        )
        command(
            f"operation_{name}_source_seed",
            f"scoreboard players set #operation_zero_source {OBJECTIVE} 0",
        )
        command(
            f"operation_{name}_apply",
            f"scoreboard players operation #operation_zero_target {OBJECTIVE} "
            f"{operation} #operation_zero_source {OBJECTIVE}",
        )
        zero_target = score(
            f"operation_{name}_target_after", "#operation_zero_target"
        )
        zero_source = score(
            f"operation_{name}_source_after", "#operation_zero_source"
        )
        if (zero_target, zero_source) != (7, 0):
            raise RuntimeError(
                f"{mode} scoreboard operation {operation} by zero changed "
                f"target/source to {zero_target}/{zero_source}; expected 7/0"
            )

    absent_holder_cases = (
        ("assign", "=", (0, 0), (3, 3)),
        ("add", "+=", (7, 0), (3, 3)),
        ("subtract", "-=", (7, 0), (-3, 3)),
        ("multiply", "*=", (0, 0), (0, 3)),
        ("divide", "/=", (7, 0), (0, 3)),
        ("remainder", "%=", (7, 0), (0, 3)),
        ("minimum", "<", (0, 0), (0, 3)),
        ("maximum", ">", (7, 0), (3, 3)),
        ("swap", "><", (0, 7), (3, 0)),
    )
    for name, operation, expected_for_absent_source, expected_for_absent_target in absent_holder_cases:
        command(
            f"operation_absent_source_{name}_target_seed",
            f"scoreboard players set #operation_absent_operand_target {OBJECTIVE} 7",
        )
        command(
            f"operation_absent_source_{name}_source_reset",
            f"scoreboard players reset #operation_absent_operand_source {OBJECTIVE}",
        )
        command(
            f"operation_absent_source_{name}_apply",
            f"scoreboard players operation #operation_absent_operand_target {OBJECTIVE} "
            f"{operation} #operation_absent_operand_source {OBJECTIVE}",
        )
        absent_source_target = score(
            f"operation_absent_source_{name}_target_after",
            "#operation_absent_operand_target",
        )
        absent_source_value = score(
            f"operation_absent_source_{name}_source_after",
            "#operation_absent_operand_source",
        )
        if (absent_source_target, absent_source_value) != expected_for_absent_source:
            raise RuntimeError(
                f"{mode} operation {operation} with absent source produced "
                f"{absent_source_target}/{absent_source_value}; expected "
                f"{expected_for_absent_source}"
            )

        command(
            f"operation_absent_target_{name}_target_reset",
            f"scoreboard players reset #operation_absent_operand_target {OBJECTIVE}",
        )
        command(
            f"operation_absent_target_{name}_source_seed",
            f"scoreboard players set #operation_absent_operand_source {OBJECTIVE} 3",
        )
        command(
            f"operation_absent_target_{name}_apply",
            f"scoreboard players operation #operation_absent_operand_target {OBJECTIVE} "
            f"{operation} #operation_absent_operand_source {OBJECTIVE}",
        )
        absent_target_value = score(
            f"operation_absent_target_{name}_target_after",
            "#operation_absent_operand_target",
        )
        absent_target_source = score(
            f"operation_absent_target_{name}_source_after",
            "#operation_absent_operand_source",
        )
        if (absent_target_value, absent_target_source) != expected_for_absent_target:
            raise RuntimeError(
                f"{mode} operation {operation} with absent target produced "
                f"{absent_target_value}/{absent_target_source}; expected "
                f"{expected_for_absent_target}"
            )

    command(
        "operation_multiply_overflow_target_seed",
        f"scoreboard players set #operation_multiply_overflow_target {OBJECTIVE} 2147483647",
    )
    command(
        "operation_multiply_overflow_source_seed",
        f"scoreboard players set #operation_multiply_overflow_source {OBJECTIVE} 2",
    )
    command(
        "operation_multiply_overflow_apply",
        f"scoreboard players operation #operation_multiply_overflow_target {OBJECTIVE} *= "
        f"#operation_multiply_overflow_source {OBJECTIVE}",
    )
    multiply_overflow = score(
        "operation_multiply_overflow_result", "#operation_multiply_overflow_target"
    )
    if multiply_overflow != -2:
        raise RuntimeError(
            f"{mode} scoreboard multiply overflow produced {multiply_overflow}; expected -2"
        )

    command("integer_bounds_function", "function function_compiler_probe:score_integer_bounds")
    minimum_after_remove = score("minimum_after_remove", "#score_min")
    maximum_after_add = score("maximum_after_add", "#score_max")
    if (minimum_after_remove, maximum_after_add) != (2_147_483_647, -2_147_483_648):
        raise RuntimeError(
            f"{mode} scoreboard integer overflow semantics changed: "
            f"min={minimum_after_remove}, max={maximum_after_add}"
        )

    command("remove_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 10")
    command("reset_seed", f"scoreboard players set #reset_seed {OBJECTIVE} 14")
    command("remove_reset_function", "function function_compiler_probe:score_remove_reset")
    if score("remove_value", "#fcprobe") != 6:
        raise RuntimeError(f"{mode} scoreboard remove did not subtract four")
    missing_score("reset_missing_value", "#score_missing")
    missing_score("reset_seeded_value", "#reset_seed")

    command("remove_absent_reset", f"scoreboard players reset #remove_absent {OBJECTIVE}")
    command(
        "remove_absent_command",
        f"scoreboard players remove #remove_absent {OBJECTIVE} 4",
    )
    if score("remove_absent_value", "#remove_absent") != -4:
        raise RuntimeError(f"{mode} remove on an absent score did not create -4")

    command("operation_target_seed", f"scoreboard players set #operation_target {OBJECTIVE} 12")
    command(
        "operation_source_reset",
        f"scoreboard players reset #operation_source {OBJECTIVE}",
    )
    command(
        "operation_missing_source",
        f"scoreboard players operation #operation_target {OBJECTIVE} += "
        f"#operation_source {OBJECTIVE}",
    )
    operation_target = score("operation_target_after_missing_source", "#operation_target")
    operation_source = score("operation_source_created", "#operation_source")
    if (operation_target, operation_source) != (12, 0):
        raise RuntimeError(
            f"{mode} operation with absent source produced target/source "
            f"{operation_target}/{operation_source}; expected 12/0"
        )

    command(
        "operation_absent_target_reset",
        f"scoreboard players reset #operation_absent_target {OBJECTIVE}",
    )
    command(
        "operation_present_source_seed",
        f"scoreboard players set #operation_present_source {OBJECTIVE} 13",
    )
    command(
        "operation_absent_target",
        f"scoreboard players operation #operation_absent_target {OBJECTIVE} += "
        f"#operation_present_source {OBJECTIVE}",
    )
    absent_target_value = score("operation_absent_target_value", "#operation_absent_target")
    if absent_target_value != 13:
        raise RuntimeError(
            f"{mode} operation with absent target produced {absent_target_value}; expected 13"
        )

    command(
        "operation_multi_target_cleanup",
        f"scoreboard players reset @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] {OBJECTIVE}",
    )
    command(
        "operation_multi_target_source_seed",
        f"scoreboard players set #operation_multi_target_source {OBJECTIVE} 2",
    )
    command(
        "operation_multi_target_selector",
        f"scoreboard players operation @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] "
        f"{OBJECTIVE} += #operation_multi_target_source {OBJECTIVE}",
    )
    command(
        "operation_multi_target_mismatch_seed",
        f"scoreboard players set #operation_multi_target_mismatch {OBJECTIVE} 0",
    )
    command(
        "operation_multi_target_mismatch_check",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] unless score @s {OBJECTIVE} "
        f"matches 2 run scoreboard players add #operation_multi_target_mismatch {OBJECTIVE} 1",
    )
    operation_multi_target_mismatches = score(
        "operation_multi_target_mismatch_count", "#operation_multi_target_mismatch"
    )
    if operation_multi_target_mismatches != 0:
        raise RuntimeError(
            f"{mode} operation with a multi-entity target produced "
            f"{operation_multi_target_mismatches} mismatched target scores; expected 0"
        )

    command(
        "operation_mixed_target_reset_one",
        f"scoreboard players reset @e[type={ACTOR_TYPE},tag={ACTOR_TAG},limit=1,sort=arbitrary] "
        f"{OBJECTIVE}",
    )
    command(
        "operation_mixed_target_source_seed",
        f"scoreboard players set #operation_mixed_target_source {OBJECTIVE} 3",
    )
    command(
        "operation_mixed_target_selector",
        f"scoreboard players operation @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] "
        f"{OBJECTIVE} += #operation_mixed_target_source {OBJECTIVE}",
    )
    command(
        "operation_mixed_target_three_count_seed",
        f"scoreboard players set #operation_mixed_target_three_count {OBJECTIVE} 0",
    )
    command(
        "operation_mixed_target_three_count",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] if score @s {OBJECTIVE} "
        f"matches 3 run scoreboard players add #operation_mixed_target_three_count "
        f"{OBJECTIVE} 1",
    )
    mixed_target_three_count = score(
        "operation_mixed_target_three_count_value", "#operation_mixed_target_three_count"
    )
    command(
        "operation_mixed_target_five_count_seed",
        f"scoreboard players set #operation_mixed_target_five_count {OBJECTIVE} 0",
    )
    command(
        "operation_mixed_target_five_count",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] if score @s {OBJECTIVE} "
        f"matches 5 run scoreboard players add #operation_mixed_target_five_count "
        f"{OBJECTIVE} 1",
    )
    mixed_target_five_count = score(
        "operation_mixed_target_five_count_value", "#operation_mixed_target_five_count"
    )
    if (mixed_target_three_count, mixed_target_five_count) != (1, 3):
        raise RuntimeError(
            f"{mode} operation across mixed present/absent selector targets produced "
            f"{mixed_target_three_count} scores of 3 and {mixed_target_five_count} of 5; "
            "expected 1 and 3"
        )

    command(
        "operation_selector_target_tag_cleanup",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] remove fc_op_target",
    )
    command(
        "operation_selector_source_tag_cleanup",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] remove fc_op_source",
    )
    command(
        "operation_selector_target_tag_seed",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG},limit=2,sort=arbitrary] add fc_op_target",
    )
    command(
        "operation_selector_source_tag_seed",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG},tag=!fc_op_target] add fc_op_source",
    )
    command(
        "operation_selector_target_count_seed",
        f"scoreboard players set #operation_selector_target_count {OBJECTIVE} 0",
    )
    command(
        "operation_selector_target_count",
        f"execute as @e[type={ACTOR_TYPE},tag=fc_op_target] run scoreboard players add "
        f"#operation_selector_target_count {OBJECTIVE} 1",
    )
    selector_target_count = score(
        "operation_selector_target_count_value", "#operation_selector_target_count"
    )
    command(
        "operation_selector_source_count_seed",
        f"scoreboard players set #operation_selector_source_count {OBJECTIVE} 0",
    )
    command(
        "operation_selector_source_count",
        f"execute as @e[type={ACTOR_TYPE},tag=fc_op_source] run scoreboard players add "
        f"#operation_selector_source_count {OBJECTIVE} 1",
    )
    selector_source_count = score(
        "operation_selector_source_count_value", "#operation_selector_source_count"
    )
    if (selector_target_count, selector_source_count) != (2, 2):
        raise RuntimeError(
            f"{mode} selector cross-product fixture has {selector_target_count} targets and "
            f"{selector_source_count} sources; expected 2 and 2"
        )
    command(
        "operation_selector_targets_seed",
        f"scoreboard players set @e[type={ACTOR_TYPE},tag=fc_op_target] {OBJECTIVE} 10",
    )
    command(
        "operation_selector_sources_seed",
        f"scoreboard players set @e[type={ACTOR_TYPE},tag=fc_op_source] {OBJECTIVE} 3",
    )
    command(
        "operation_selector_source_adjust_one",
        f"scoreboard players add @e[type={ACTOR_TYPE},tag=fc_op_source,limit=1,sort=arbitrary] "
        f"{OBJECTIVE} 2",
    )
    command(
        "operation_selector_cross_product",
        f"scoreboard players operation @e[type={ACTOR_TYPE},tag=fc_op_target] {OBJECTIVE} += "
        f"@e[type={ACTOR_TYPE},tag=fc_op_source] {OBJECTIVE}",
    )
    command(
        "operation_selector_target_result_mismatch_seed",
        f"scoreboard players set #operation_selector_target_result_mismatch {OBJECTIVE} 0",
    )
    command(
        "operation_selector_target_result_mismatch",
        f"execute as @e[type={ACTOR_TYPE},tag=fc_op_target] unless score @s {OBJECTIVE} "
        f"matches 18 run scoreboard players add #operation_selector_target_result_mismatch "
        f"{OBJECTIVE} 1",
    )
    selector_target_result_mismatches = score(
        "operation_selector_target_result_mismatches",
        "#operation_selector_target_result_mismatch",
    )
    command(
        "operation_selector_source_result_mismatch_seed",
        f"scoreboard players set #operation_selector_source_result_mismatch {OBJECTIVE} 0",
    )
    command(
        "operation_selector_source_result_mismatch",
        f"execute as @e[type={ACTOR_TYPE},tag=fc_op_source] unless score @s {OBJECTIVE} "
        f"matches 3..5 run scoreboard players add #operation_selector_source_result_mismatch "
        f"{OBJECTIVE} 1",
    )
    selector_source_result_mismatches = score(
        "operation_selector_source_result_mismatches",
        "#operation_selector_source_result_mismatch",
    )
    if selector_target_result_mismatches != 0 or selector_source_result_mismatches != 0:
        raise RuntimeError(
            f"{mode} selector cross-product produced {selector_target_result_mismatches} "
            f"bad targets and {selector_source_result_mismatches} changed sources; expected 0/0"
        )
    command(
        "operation_selector_target_tag_remove",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG},tag=fc_op_target] remove fc_op_target",
    )
    command(
        "operation_selector_source_tag_remove",
        f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG},tag=fc_op_source] remove fc_op_source",
    )

    command(
        "operation_selector_mixed_source_cleanup",
        f"scoreboard players reset @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] {OBJECTIVE}",
    )
    command(
        "operation_selector_mixed_source_seed_three",
        f"scoreboard players set @e[type={ACTOR_TYPE},tag={ACTOR_TAG},limit=3,sort=arbitrary] "
        f"{OBJECTIVE} 5",
    )
    command(
        "operation_selector_mixed_source_target_seed",
        f"scoreboard players set #operation_selector_mixed_source_target {OBJECTIVE} 10",
    )
    command(
        "operation_selector_mixed_source_apply",
        f"scoreboard players operation #operation_selector_mixed_source_target {OBJECTIVE} += "
        f"@e[type={ACTOR_TYPE},tag={ACTOR_TAG}] {OBJECTIVE}",
    )
    mixed_source_target = score(
        "operation_selector_mixed_source_target_after",
        "#operation_selector_mixed_source_target",
    )
    command(
        "operation_selector_mixed_source_zero_count_seed",
        f"scoreboard players set #operation_selector_mixed_source_zero_count {OBJECTIVE} 0",
    )
    command(
        "operation_selector_mixed_source_zero_count",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] if score @s {OBJECTIVE} "
        f"matches 0 run scoreboard players add #operation_selector_mixed_source_zero_count "
        f"{OBJECTIVE} 1",
    )
    mixed_source_zero_count = score(
        "operation_selector_mixed_source_zero_count_value",
        "#operation_selector_mixed_source_zero_count",
    )
    command(
        "operation_selector_mixed_source_five_count_seed",
        f"scoreboard players set #operation_selector_mixed_source_five_count {OBJECTIVE} 0",
    )
    command(
        "operation_selector_mixed_source_five_count",
        f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] if score @s {OBJECTIVE} "
        f"matches 5 run scoreboard players add #operation_selector_mixed_source_five_count "
        f"{OBJECTIVE} 1",
    )
    mixed_source_five_count = score(
        "operation_selector_mixed_source_five_count_value",
        "#operation_selector_mixed_source_five_count",
    )
    if (mixed_source_target, mixed_source_zero_count, mixed_source_five_count) != (25, 1, 3):
        raise RuntimeError(
            f"{mode} mixed source selector produced target={mixed_source_target}, "
            f"zero-source-count={mixed_source_zero_count}, "
            f"five-source-count={mixed_source_five_count}; expected 25/1/3"
        )

    command("recreate_cleanup", "scoreboard objectives remove fc_recreate")
    command("recreate_add_first", "scoreboard objectives add fc_recreate dummy")
    command("recreate_seed", "scoreboard players set #recreate fc_recreate 31")
    command("recreate_remove", "scoreboard objectives remove fc_recreate")
    command("recreate_add_second", "scoreboard objectives add fc_recreate dummy")
    missing_score("recreate_old_score_absent", "#recreate", "fc_recreate")
    command("recreate_new_seed", "scoreboard players set #recreate fc_recreate 9")
    if score("recreate_new_value", "#recreate", "fc_recreate") != 9:
        raise RuntimeError(f"{mode} recreated objective retained stale score state")

    command("store_fail_seed", "scoreboard players set #store_success fc_probe 1")
    command(
        "store_fail_result",
        "execute store success score #store_success fc_probe run "
        "function function_compiler_probe:quota_condition_failure",
    )
    failure_success = score("store_fail_success", "#store_success")
    command("store_missing_score_seed", "scoreboard players set #store_success fc_probe 1")
    command(
        "store_missing_score_result",
        "execute store success score #store_success fc_probe run "
        "scoreboard players get #score_missing fc_probe",
    )
    missing_score_success = score("store_missing_score_success", "#store_success")
    if failure_success != 0 or missing_score_success != 0:
        raise RuntimeError(
            f"{mode} execute store success failed-command results were "
            f"{failure_success}, {missing_score_success}"
        )
    command(
        "store_success_result",
        "execute store success score #store_success fc_probe run "
        "scoreboard players set #fcprobe fc_probe -17",
    )
    stored_success_value = score("store_success_value", "#store_success")
    if stored_success_value != 1:
        raise RuntimeError(f"{mode} execute store success did not record success")

    command("store_add_result_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 5")
    command("store_add_result_function", "function function_compiler_probe:score_store_add_result")
    stored_add_result = score("store_add_result", "#stored_add_result")
    add_result_score = score("store_add_result_score", "#fcprobe")
    if stored_add_result != 12 or add_result_score != 12:
        raise RuntimeError(
            f"{mode} ScoreAdd function result was {stored_add_result} with state "
            f"{add_result_score}; expected 12 for both"
        )

    command("store_add_success_seed", f"scoreboard players set #fcprobe {OBJECTIVE} 5")
    command("store_add_success_function", "function function_compiler_probe:score_store_add_success")
    stored_add_success = score("store_add_success", "#stored_add_success")
    add_success_score = score("store_add_success_score", "#fcprobe")
    if stored_add_success != 1 or add_success_score != 12:
        raise RuntimeError(
            f"{mode} ScoreAdd success callback wrote {stored_add_success} with state "
            f"{add_success_score}; expected 1 and 12"
        )

    (REPORT_DIR / f"{mode}.scoreboard-semantics.json").write_text(
        json.dumps(observations, indent=2) + "\n",
        encoding="utf-8",
    )
    return observations


def run_delegation_contract(client: RconClient, mode: str) -> dict[str, object]:
    """Check the "stays on the vanilla path" claims by measurement.

    Two classes of coverage rows rest on delegation rather than on a
    differential oracle: the selector-shaped scoreboard rows, which the compiler
    declines because every operand is an entity selector, and the
    client-packet-only command families, which have no server-side observable
    effect at all. Prose is not a checkable claim, so the mod exposes per
    function specialization counters on `function_compiler_probe status` and this
    function asserts on them.

    The measurement is held accountable by a control, and the gate is the
    control's own reading rather than a configuration flag. If the control's
    *compiled* counter is nonzero, the measurement is live and the declined
    fixtures must read zero in both directions; if it is zero, this arm
    specializes nothing, so a zero reading elsewhere would be meaningless and
    the arm is recorded as not exercising the contract. Counting compiled
    commands in the arm's own configuration would under-check it: `instrument-only`
    runs with the scoreboard-prototype flag off yet still compiles specialized
    commands, and its contract matters just as much as the others'.

    The control's *executed* counter is additionally gated on the metrics flag,
    because that counter is only wired when instrumentation is enabled.
    """

    observations: dict[str, object] = {}
    if mode == "mod-free-vanilla":
        observations["status_available"] = False
        return observations
    observations["status_available"] = True

    before = client.command("function_compiler_probe status")
    metrics_enabled = " score_add_metrics_enabled=true" in before
    observations["score_add_metrics_enabled"] = metrics_enabled
    control_compiled_before = status_counter(before, "delegation_control_compiled")
    control_executed_before = status_counter(before, "delegation_control_executed")
    observations["control_compiled"] = control_compiled_before
    observations["control_executed_before"] = control_executed_before
    # The contract is only exercisable where something in this arm specializes.
    measurement_live = control_compiled_before >= 1
    observations["measurement_live"] = measurement_live
    if not measurement_live:
        observations["counter_checks_skipped"] = (
            "no specialized command was compiled in this arm, so a zero "
            "reading on the declined fixtures would prove nothing"
        )

    control_response = client.command(
        "function function_compiler_probe:score_delegation_positive"
    )
    after_control = client.command("function_compiler_probe status")
    control_executed_after = status_counter(after_control, "delegation_control_executed")
    observations["control_executed_after"] = control_executed_after
    if measurement_live and metrics_enabled:
        if control_executed_after <= control_executed_before:
            raise RuntimeError(
                f"{mode} delegation control did not execute a specialized "
                f"command: {control_executed_before} -> {control_executed_after}, "
                f"response={control_response!r}"
            )

    if measurement_live:
        selector_compiled = status_counter(
            after_control, "delegation_selector_compiled"
        )
        selector_executed = status_counter(
            after_control, "delegation_selector_executed"
        )
        client_packet_compiled = status_counter(
            after_control, "delegation_client_packet_compiled"
        )
        client_packet_executed = status_counter(
            after_control, "delegation_client_packet_executed"
        )
        if (
            selector_compiled
            or selector_executed
            or client_packet_compiled
            or client_packet_executed
        ):
            raise RuntimeError(
                f"{mode} a delegation-contract fixture was specialized: "
                f"selector={selector_compiled}/{selector_executed}, "
                f"client_packet={client_packet_compiled}/{client_packet_executed}"
            )

    selector_response = client.command(
        "function function_compiler_probe:score_selector_declined"
    )
    client_packet_response = client.command(
        "function function_compiler_probe:state_machine_client_packet"
    )
    after = client.command("function_compiler_probe status")
    observations.update(
        {
            "selector_compiled": status_counter(after, "delegation_selector_compiled"),
            "selector_executed": status_counter(after, "delegation_selector_executed"),
            "client_packet_compiled": status_counter(
                after, "delegation_client_packet_compiled"
            ),
            "client_packet_executed": status_counter(
                after, "delegation_client_packet_executed"
            ),
            "selector_response": selector_response,
            "client_packet_response": client_packet_response,
        }
    )
    for label, response in (
        ("selector", selector_response),
        ("client_packet", client_packet_response),
    ):
        if not response.startswith("Running function "):
            raise RuntimeError(
                f"{mode} delegation-contract {label} fixture was not invoked: "
                f"{response!r}"
            )
        if "Unknown" in response or "Incorrect" in response:
            raise RuntimeError(
                f"{mode} delegation-contract {label} fixture was rejected: "
                f"{response!r}"
            )
    if measurement_live and (
        observations["selector_compiled"]
        or observations["selector_executed"]
        or observations["client_packet_compiled"]
        or observations["client_packet_executed"]
    ):
        raise RuntimeError(
            f"{mode} a delegation-contract fixture was specialized after "
            f"invocation: selector={observations['selector_compiled']}/"
            f"{observations['selector_executed']}, "
            f"client_packet={observations['client_packet_compiled']}/"
            f"{observations['client_packet_executed']}"
        )
    return observations


def run_control_flow_fallback_cases(
    client: RconClient, mode: str, server_root: Path
) -> dict[str, object]:
    results: dict[str, object] = {}

    def run_case(
        name: str,
        function: str,
        expected_score: int,
        assert_single_region_for_backend: bool = False,
        expected_backend_regions: int | None = None,
        store_success_holder: str | None = None,
        expected_store_success: int | None = None,
        store_result_holder: str | None = None,
        expected_store_result: int | None = None,
    ) -> None:
        client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        client.command(f"scoreboard players reset #syntax_missing {OBJECTIVE}")
        if store_success_holder is not None:
            client.command(f"scoreboard players set {store_success_holder} {OBJECTIVE} 1")
        if store_result_holder is not None:
            client.command(f"scoreboard players set {store_result_holder} {OBJECTIVE} -1")
        backend_region_metric: str | None = None
        backend_regions_before: int | None = None
        expected_backend_region_count = (
            expected_backend_regions
            if expected_backend_regions is not None
            else (1 if assert_single_region_for_backend else None)
        )
        if expected_backend_region_count is not None:
            backend_region_metric = {
                "fused-interpreted": "fused_regions_executed",
                "bytecode-emitted": "bytecode_regions_executed",
            }.get(mode)
            if backend_region_metric is not None:
                backend_regions_before = status_counter(
                    client.command("function_compiler_probe status"),
                    backend_region_metric,
                )
        function_response = client.command(f"function function_compiler_probe:{function}")
        actual_score = read_score(client, HOLDER, OBJECTIVE)
        if actual_score != expected_score:
            raise RuntimeError(
                f"{mode} {function} resumed with score {actual_score}; "
                f"expected {expected_score}"
            )
        case_result: dict[str, object] = {
            "function": function,
            "response": function_response,
            "score": actual_score,
        }
        if store_success_holder is not None:
            stored_success = read_score(
                client,
                store_success_holder,
                OBJECTIVE,
            )
            if (
                expected_store_success is not None
                and stored_success != expected_store_success
            ):
                raise RuntimeError(
                    f"{mode} {function} stored success {stored_success}; "
                    f"expected {expected_store_success}"
                )
            case_result["stored_success"] = stored_success
        if store_result_holder is not None:
            stored_result = read_score(client, store_result_holder, OBJECTIVE)
            if (
                expected_store_result is not None
                and stored_result != expected_store_result
            ):
                raise RuntimeError(
                    f"{mode} {function} stored result {stored_result}; "
                    f"expected {expected_store_result}"
                )
            case_result["stored_result"] = stored_result
        if backend_region_metric is not None and backend_regions_before is not None:
            backend_regions_after = status_counter(
                client.command("function_compiler_probe status"),
                backend_region_metric,
            )
            backend_region_delta = backend_regions_after - backend_regions_before
            if backend_region_delta != expected_backend_region_count:
                raise RuntimeError(
                    f"{mode} {function} executed {backend_region_delta} backend "
                    f"regions; expected {expected_backend_region_count}"
                )
            case_result["backend_region_metrics"] = {
                "counter": backend_region_metric,
                "executed_delta": backend_region_delta,
            }
        results[name] = case_result

    def run_quota_sweep(name: str, function: str, expected_high_score: int) -> None:
        scores: dict[int, int] = {}
        responses: list[dict[str, object]] = []
        for quota in range(17):
            quota_response = client.command(f"gamerule {LEVEL} {quota}")
            if str(quota) not in quota_response:
                raise RuntimeError(
                    f"Could not set {mode} callback sequence limit to {quota}: "
                    f"{quota_response!r}"
                )
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            client.command(f"scoreboard players reset #syntax_missing {OBJECTIVE}")
            function_response = client.command(
                f"function function_compiler_probe:{function}"
            )
            actual_score = read_score(client, HOLDER, OBJECTIVE)
            scores[quota] = actual_score
            responses.append(
                {
                    "quota": quota,
                    "function_response": function_response,
                    "score": actual_score,
                }
            )
        if scores[16] != expected_high_score:
            raise RuntimeError(
                f"{mode} {function} at sequence limit 16 ended with "
                f"score {scores[16]}; expected {expected_high_score}"
            )
        results[name] = {
            "function": function,
            "scores_by_quota": scores,
            "commands": responses,
        }
        client.command(f"gamerule {LEVEL} 65536")

    client.command(f"gamerule {LEVEL} 65536")
    run_case("vanilla_fallback_resume", "quota_vanilla_fallback_resume", 11)
    client.command(f"scoreboard players reset #syntax_missing {OBJECTIVE}")
    run_case("syntax_exception_resume", "quota_runtime_syntax_exception", 1)
    run_case("return_run_nested_exception", "quota_return_run_exception", 3)
    run_case("execute_if_nested_exception", "quota_execute_if_exception", 3)
    run_case("execute_unless_nested_exception", "quota_execute_unless_exception", 14)
    run_case(
        "execute_if_return_fail_discards_fused_tails",
        "fused_execute_if_discard_outer",
        31,
        assert_single_region_for_backend=True,
    )
    run_case(
        "execute_unless_return_fail_runs_branch_discards_fused_tails",
        "fused_execute_unless_discard_outer",
        1032,
        assert_single_region_for_backend=True,
    )
    run_case(
        "execute_store_success_return_fail_discards_fused_tails",
        "fused_execute_store_discard_outer",
        32,
        assert_single_region_for_backend=True,
        store_success_holder="#nested_store_success",
        expected_store_success=0,
    )
    run_case(
        "execute_store_success_return_value_discards_fused_tails",
        "fused_execute_store_success_return_value_outer",
        32,
        assert_single_region_for_backend=True,
        store_success_holder="#nested_store_success",
        expected_store_success=1,
    )
    run_case(
        "execute_store_success_nested_return_discards_fused_tails",
        "fused_execute_store_success_nested_return_outer",
        37,
        assert_single_region_for_backend=True,
        store_success_holder="#nested_store_success",
        expected_store_success=1,
    )
    run_case(
        "execute_store_success_nested_fail_discards_fused_tails",
        "fused_execute_store_success_nested_fail_outer",
        37,
        assert_single_region_for_backend=True,
        store_success_holder="#nested_store_success",
        expected_store_success=0,
    )
    run_case(
        "execute_store_result_nested_return_discards_fused_tails",
        "fused_execute_store_result_nested_return_outer",
        37,
        assert_single_region_for_backend=True,
        store_result_holder="#nested_store_result",
        expected_store_result=7,
    )
    run_case(
        "execute_store_result_return_value_discards_fused_tails",
        "fused_execute_store_result_discard_outer",
        32,
        assert_single_region_for_backend=True,
        store_result_holder="#nested_store_result",
        expected_store_result=7,
    )
    run_case(
        "execute_store_result_return_fail_discards_fused_tails",
        "fused_execute_store_result_fail_outer",
        32,
        assert_single_region_for_backend=True,
        store_result_holder="#nested_store_result",
        expected_store_result=0,
    )
    # The three cbx cases complete the callback-context x child-outcome matrix.
    # cbx_return_run_fail: the child's +10/+20 region executes and both pending
    # tail regions (child and parent) are discarded, so only the child's region
    # counts. cbx_nested_fail: the child's +10/+20 region executes AND the
    # parent's +1000/+1000 tail resumes, so two regions count - unlike the
    # store/if siblings, whose children carry only single adds and no region of
    # their own. cbx_unless_success: the child returns a value (compile-time
    # return, one lone add, no region) and the unless branch is skipped, so
    # only the parent tail region counts.
    run_case(
        "return_run_child_fail_discards_fused_tails",
        "cbx_return_run_fail",
        31,
        expected_backend_regions=1,
    )
    run_case(
        "nested_child_fail_resumes_parent_tail",
        "cbx_nested_fail",
        2031,
        expected_backend_regions=2,
    )
    run_case(
        "execute_unless_child_success_skips_branch",
        "cbx_unless_success",
        2002,
        expected_backend_regions=1,
    )
    run_quota_sweep(
        "return_run_nested_exception_quota_sweep",
        "quota_return_run_exception",
        3,
    )
    run_quota_sweep(
        "execute_if_nested_exception_quota_sweep",
        "quota_execute_if_exception",
        3,
    )
    run_quota_sweep(
        "execute_unless_nested_exception_quota_sweep",
        "quota_execute_unless_exception",
        14,
    )
    run_quota_sweep(
        "execute_store_result_nested_return_quota_sweep",
        "fused_execute_store_result_nested_return_outer",
        37,
    )
    run_quota_sweep(
        "execute_store_success_nested_return_quota_sweep",
        "fused_execute_store_success_nested_return_outer",
        37,
    )
    run_quota_sweep(
        "execute_store_success_nested_fail_quota_sweep",
        "fused_execute_store_success_nested_fail_outer",
        37,
    )

    store_callback_scores: dict[str, dict[str, int]] = {}
    store_callback_responses: dict[str, str] = {}
    expected_store_callback_scores = {
        str(quota): {
            "score": 0 if quota < 5 else (2 if quota < 9 else 4),
            "stored_result": -1,
            "stored_success": -1,
        }
        for quota in range(17)
    }
    for quota in range(17):
        quota_response = client.command(f"gamerule {LEVEL} {quota}")
        if str(quota) not in quota_response:
            raise RuntimeError(
                f"Could not set {mode} store-callback sequence limit to {quota}: "
                f"{quota_response!r}"
            )
        client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
        client.command(f"scoreboard players set #nested_store_result {OBJECTIVE} -1")
        client.command(f"scoreboard players set #nested_store_success {OBJECTIVE} -1")
        client.command(f"scoreboard players reset #syntax_missing {OBJECTIVE}")
        response = client.command(
            "function function_compiler_probe:quota_execute_store_exception"
        )
        store_callback_scores[str(quota)] = {
            "score": read_score(client, HOLDER, OBJECTIVE),
            "stored_result": read_score(client, "#nested_store_result", OBJECTIVE),
            "stored_success": read_score(client, "#nested_store_success", OBJECTIVE),
        }
        store_callback_responses[str(quota)] = response
    if store_callback_scores != expected_store_callback_scores:
        raise RuntimeError(
            f"{mode} execute-store callback results after nested syntax error "
            f"were {store_callback_scores!r}; expected "
            f"{expected_store_callback_scores!r}"
        )
    client.command(f"gamerule {LEVEL} 65536")
    client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
    client.command(f"scoreboard players set #nested_store_result {OBJECTIVE} -1")
    client.command(f"scoreboard players set #nested_store_success {OBJECTIVE} -1")
    client.command(f"scoreboard players reset #syntax_missing {OBJECTIVE}")
    store_callback_debug = run_debug_trace_fixture(
        client,
        mode,
        server_root,
        "function_compiler_probe:quota_execute_store_exception",
        expected_score=store_callback_scores["16"]["score"],
        expected_command_events=6,
    )
    store_callback_debug["stored_result"] = read_score(
        client, "#nested_store_result", OBJECTIVE
    )
    store_callback_debug["stored_success"] = read_score(
        client, "#nested_store_success", OBJECTIVE
    )
    store_callback_debug.pop("response", None)
    if (
        store_callback_debug["stored_result"] != -1
        or store_callback_debug["stored_success"] != -1
    ):
        raise RuntimeError(
            f"{mode} execute-store callback wrote after nested syntax error: "
            f"{store_callback_debug!r}"
        )
    results["execute_store_nested_exception"] = {
        "function": "quota_execute_store_exception",
        "scores_by_quota": store_callback_scores,
        "function_responses_by_quota": store_callback_responses,
        "debug_trace": store_callback_debug,
    }
    return results


def run_command_callback_metrics_fixture(
    client: RconClient,
    mode: str,
    measure_callbacks: bool,
) -> dict[str, object]:
    tag = "fc_callback_metrics_actor"
    client.command(f"kill @e[type={ACTOR_TYPE},tag={tag}]")
    client.command("forceload add 0 0")
    for index, position in enumerate(
        ("0.5 100 0.5", "1.5 100 0.5", "2.5 100 0.5")
    ):
        response = client.command(
            f'summon {ACTOR_TYPE} {position} '
            f'{{NoGravity:1b,Invisible:1b,Invulnerable:1b,Tags:["{tag}"]}}'
        )
        if "summoned" not in response.casefold():
            raise RuntimeError(
                f"{mode} could not summon callback-metrics actor {index}: {response!r}"
            )

    client.command(f"scoreboard players set #callback_metrics {OBJECTIVE} 0")
    before_status: str | None = None
    counters_before: tuple[int, int] | None = None
    use_metric_command = measure_callbacks and mode != "mod-free-vanilla"
    if use_metric_command:
        before_status = client.command("function_compiler_probe status")
        generic_match = re.search(r"generic_leaf_callbacks=(\d+)", before_status)
        optimized_match = re.search(
            r"optimized_score_add_leaf_callbacks=(\d+)", before_status
        )
        if generic_match is None or optimized_match is None:
            raise RuntimeError(f"{mode} status omitted callback metric counters")
        counters_before = (int(generic_match.group(1)), int(optimized_match.group(1)))
        function_response = client.command(
            "function_compiler_probe measure "
            "function_compiler_probe:callback_metrics"
        )
    else:
        function_response = client.command(
            "function function_compiler_probe:callback_metrics"
        )

    final_score = read_score(client, "#callback_metrics", OBJECTIVE)
    client.command(f"scoreboard players set #callback_actor_count {OBJECTIVE} 0")
    client.command(
        f"execute as @e[type={ACTOR_TYPE},tag={tag}] "
        f"if score @s {OBJECTIVE} matches 9 run "
        f"scoreboard players add #callback_actor_count {OBJECTIVE} 1"
    )
    actor_count = read_score(client, "#callback_actor_count", OBJECTIVE)
    if final_score != 6 or actor_count != 3:
        raise RuntimeError(
            f"{mode} callback metric fixture state was score={final_score}, "
            f"actors={actor_count}; expected score=6 and actors=3"
        )

    metric_deltas = None
    if use_metric_command:
        assert counters_before is not None
        after_status = client.command("function_compiler_probe status")
        generic_match = re.search(r"generic_leaf_callbacks=(\d+)", after_status)
        optimized_match = re.search(
            r"optimized_score_add_leaf_callbacks=(\d+)", after_status
        )
        if generic_match is None or optimized_match is None:
            raise RuntimeError(f"{mode} status omitted callback metric counters")
        generic_delta = int(generic_match.group(1)) - counters_before[0]
        optimized_delta = int(optimized_match.group(1)) - counters_before[1]
        expected_optimized = 2 if mode in {
            "score-add-on", "score-add-timed", "fused-interpreted",
            "bytecode-emitted", "bytecode-compile-failure",
        } else 0
        expected_generic = 7 - expected_optimized
        if (generic_delta, optimized_delta) != (
            expected_generic, expected_optimized
        ):
            raise RuntimeError(
                f"{mode} command callback metrics were generic={generic_delta}, "
                f"optimized={optimized_delta}; expected generic={expected_generic}, "
                f"optimized={expected_optimized}"
            )
        metric_deltas = {
            "generic_leaf_callbacks": generic_delta,
            "optimized_score_add_leaf_callbacks": optimized_delta,
            "total_ordinary_leaf_callbacks": generic_delta + optimized_delta,
        }

    return {
        "function_response": function_response,
        "score": final_score,
        "forked_actor_count": actor_count,
        "callback_metrics": metric_deltas,
    }


def run_fork_limit_fixture(client: RconClient, mode: str) -> dict[str, object]:
    all_results: list[dict[str, object]] = []
    for match_count in FORK_MATCH_COUNTS:
        client.command(f"tag @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] remove {ACTOR_TAG}")
        if match_count:
            client.command(
                f"tag @e[type={ACTOR_TYPE},tag={ACTOR_POOL_TAG},"
                f"limit={match_count},sort=arbitrary] add {ACTOR_TAG}"
            )
        client.command(f"scoreboard players set #actor_count {OBJECTIVE} 0")
        client.command(
            f"execute as @e[type={ACTOR_TYPE},tag={ACTOR_TAG}] "
            f"run scoreboard players add #actor_count {OBJECTIVE} 1"
        )
        actual_match_count = read_score(client, "#actor_count", OBJECTIVE)
        if actual_match_count != match_count:
            raise RuntimeError(
                f"{mode} configured {match_count} fork matches but found {actual_match_count}"
            )

        match_results: list[dict[str, object]] = []
        for fork_limit in FORK_LIMITS:
            fork_response = client.command(
                f"gamerule minecraft:max_command_forks {fork_limit}"
            )
            if str(fork_limit) not in fork_response:
                raise RuntimeError(
                    f"Could not set {mode} max_command_forks to {fork_limit}: "
                    f"{fork_response!r}"
                )
            quota_response = client.command(f"gamerule {LEVEL} 64")
            if "64" not in quota_response:
                raise RuntimeError(
                    f"Could not set {mode} sequence quota to 64: {quota_response!r}"
                )
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            function_response = client.command(
                "function function_compiler_probe:quota_fork_four"
            )
            score_response = client.command(
                f"scoreboard players get {HOLDER} {OBJECTIVE}"
            )
            match = re.search(r"has (-?\d+)", score_response)
            if match is None:
                raise RuntimeError(
                    f"Could not parse {mode} fork limit {fork_limit} score: "
                    f"{score_response!r}"
                )
            score = int(match.group(1))
            if not 0 <= score <= match_count:
                raise RuntimeError(
                    f"{mode} fork limit {fork_limit} with {match_count} matches "
                    f"produced impossible score {score}"
                )

            client.command(f"scoreboard players set #fork_overflow_effect {OBJECTIVE} 0")
            client.command(f"scoreboard players set #fork_overflow_followup {OBJECTIVE} 0")
            overflow_function_response = client.command(
                "function function_compiler_probe:quota_fork_overflow_resume"
            )
            overflow_effect = read_score(client, "#fork_overflow_effect", OBJECTIVE)
            overflow_followup = read_score(
                client, "#fork_overflow_followup", OBJECTIVE
            )
            if overflow_effect != score or overflow_followup != 10:
                raise RuntimeError(
                    f"{mode} fork overflow at limit {fork_limit} with "
                    f"{match_count} matches produced effect={overflow_effect}, "
                    f"followup={overflow_followup}; expected effect={score}, "
                    "followup=10"
                )
            match_results.append(
                {
                    "fork_limit": fork_limit,
                    "gamerule": fork_response,
                    "function": function_response,
                    "score": score,
                    "score_response": score_response,
                    "overflow_function": overflow_function_response,
                    "overflow_effect": overflow_effect,
                    "overflow_followup": overflow_followup,
                }
            )

        scores = [int(item["score"]) for item in match_results]
        if any(left > right for left, right in zip(scores, scores[1:])):
            raise RuntimeError(
                f"{mode} fork effects decreased as max_command_forks increased: {scores}"
            )
        if scores[-1] != match_count:
            raise RuntimeError(
                f"{mode} fork limit {FORK_LIMITS[-1]} completed {scores[-1]} effects "
                f"with {match_count} matching entities"
            )
        all_results.append(
            {
                "match_count": match_count,
                "runs": match_results,
                "scores_by_fork_limit": dict(zip(FORK_LIMITS, scores)),
            }
        )

    client.command("gamerule minecraft:max_command_forks 65536")
    client.command(f"gamerule {LEVEL} 65536")

    # Batch 15: the remaining selector shapes for the fork modifier's
    # selection surface. The world spawn is pinned first because the
    # `distance=` anchor is the command source at the world spawn, which a
    # freshly generated world randomizes - without the pin the two distance
    # shapes are not reproducible across runs (measured: the same fixture
    # scored 1 in one fresh world and 101 in another).
    spawn_response = client.command("setworldspawn 0 64 0")
    if "Set" not in spawn_response or "0" not in spawn_response:
        raise RuntimeError(
            f"{mode} could not pin the world spawn: {spawn_response!r}"
        )
    for tag in ("fc_fork_type", "fc_fork_outside", "fc_fork_subset"):
        client.command(f"kill @e[tag={tag}]")
    for position in ("1 64 0", "3 64 0", "2 64 2"):
        response = client.command(
            f"summon minecraft:armor_stand {position} "
            '{NoGravity:1b,Invisible:1b,Invulnerable:1b,Tags:["fc_fork_type"]}'
        )
        if "summoned" not in response.casefold():
            raise RuntimeError(f"{mode} could not summon type actor: {response!r}")
    decoy_response = client.command(
        "summon minecraft:creeper 0 64 5 "
        '{NoGravity:1b,Invulnerable:1b,PersistenceRequired:1b,'
        'Tags:["fc_fork_type"]}'
    )
    if "summoned" not in decoy_response.casefold():
        raise RuntimeError(f"{mode} could not summon creeper decoy: {decoy_response!r}")
    for tag, positions in (
        ("fc_fork_outside", ("10 64 0", "20 64 0")),
        ("fc_fork_subset", ("2 64 0", "6 64 0")),
    ):
        for position in positions:
            response = client.command(
                f"summon minecraft:armor_stand {position} "
                '{NoGravity:1b,Invisible:1b,Invulnerable:1b,'
                f'Tags:["{tag}"]}}'
            )
            if "summoned" not in response.casefold():
                raise RuntimeError(
                    f"{mode} could not summon {tag} actor: {response!r}"
                )
    time.sleep(1)

    # Vanilla-observed maps over max_command_forks 1-12:
    # type filter (two stands, a creeper decoy excluded) forks both stands
    # from cap 3 (cap 1 the maximum-context error, cap 2 silent truncation);
    # the all-outside distance shape never matches; the distance subset shape
    # forks its single matching actor from cap 2.
    expected_shape_scores = {
        "quota_fork_type_filter": {
            1: 1,
            2: 1,
            **{cap: 21 for cap in range(3, 13)},
        },
        "quota_fork_distance_filter": {cap: 1 for cap in FORK_LIMITS},
        "quota_fork_distance_subset": {
            1: 1,
            **{cap: 101 for cap in range(2, 13)},
        },
    }
    selector_shape_cases: list[dict[str, object]] = []
    for shape in expected_shape_scores:
        shape_results: list[dict[str, object]] = []
        for fork_limit in FORK_LIMITS:
            fork_response = client.command(
                f"gamerule minecraft:max_command_forks {fork_limit}"
            )
            if str(fork_limit) not in fork_response:
                raise RuntimeError(
                    f"Could not set {mode} max_command_forks to {fork_limit} "
                    f"for the {shape} shape: {fork_response!r}"
                )
            client.command(f"gamerule {LEVEL} 64")
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            function_response = client.command(
                f"function function_compiler_probe:{shape}"
            )
            score_response = client.command(
                f"scoreboard players get {HOLDER} {OBJECTIVE}"
            )
            match = re.search(r"has (-?\d+)", score_response)
            if match is None:
                raise RuntimeError(
                    f"Could not parse {mode} {shape} fork limit {fork_limit} "
                    f"score: {score_response!r}"
                )
            score = int(match.group(1))
            shape_results.append(
                {
                    "fork_limit": fork_limit,
                    "gamerule": fork_response,
                    "function": function_response,
                    "score": score,
                    "score_response": score_response,
                }
            )
        selector_shape_cases.append(
            {
                "shape": shape,
                "runs": shape_results,
                "scores_by_fork_limit": {
                    item["fork_limit"]: item["score"] for item in shape_results
                },
            }
        )
    return {
        "match_cases": all_results,
        "selector_shape_cases": selector_shape_cases,
    }


# MO-09 identity actors: three tagged armor stands at distinct positions with
# distinct scoreboard values, summoned in canonical order a, b, c. The swap
# chain decoder below reads the fork selection order back from scoreboard
# state: after two `#fork_order_acc >< @s` branches with the accumulator at
# the marker, the first forked actor holds the marker, the accumulator holds
# the second actor's original value, and the second actor holds the first
# actor's original value.
FORK_ORDER_ACTOR_VALUES = {
    "fc_fork_order_a": 2,
    "fc_fork_order_b": 3,
    "fc_fork_order_c": 5,
}
FORK_ORDER_ACTOR_POSITIONS = {
    "fc_fork_order_a": "32.5 100 0.5",
    "fc_fork_order_b": "33.5 100 0.5",
    "fc_fork_order_c": "34.5 100 0.5",
}
FORK_ORDER_MARKER = 100


def reset_fork_order_actors(client: RconClient, objective: str, tags: tuple[str, ...]) -> None:
    client.command(f"scoreboard players set #fork_order_acc {objective} {FORK_ORDER_MARKER}")
    for tag in tags:
        client.command(
            f"scoreboard players set @e[tag={tag},limit=1] {objective} "
            f"{FORK_ORDER_ACTOR_VALUES[tag]}"
        )


def read_fork_order_scores(
    client: RconClient, objective: str, tags: tuple[str, ...]
) -> dict[str, int | None]:
    scores: dict[str, int | None] = {}
    for tag in tags:
        response = client.command(f"scoreboard players get @e[tag={tag},limit=1] {objective}")
        match = re.search(r"has (-?\d+)", response)
        scores[tag] = int(match.group(1)) if match else None
    return scores


def decode_fork_order(
    client: RconClient, objective: str, tags: tuple[str, ...]
) -> tuple[str, str]:
    scores = read_fork_order_scores(client, objective, tags)
    first_candidates = [tag for tag in tags if scores[tag] == FORK_ORDER_MARKER]
    if len(first_candidates) != 1:
        raise RuntimeError(f"fork-order decode first pass was ambiguous: {scores!r}")
    first = first_candidates[0]
    second_candidates = [
        tag for tag in tags if tag != first and scores[tag] != FORK_ORDER_ACTOR_VALUES[tag]
    ]
    if len(second_candidates) != 1:
        raise RuntimeError(f"fork-order decode second pass was ambiguous: {scores!r}")
    second = second_candidates[0]
    accumulator = read_score(client, "#fork_order_acc", objective)
    if accumulator != FORK_ORDER_ACTOR_VALUES[second]:
        raise RuntimeError(
            f"fork-order decode accumulator was {accumulator}; expected "
            f"{FORK_ORDER_ACTOR_VALUES[second]} for second actor {second}: {scores!r}"
        )
    return (first, second)


def fork_order_identity_swap(client: RconClient, objective: str, sort: str) -> str:
    return client.command(
        "execute positioned 32 100 0 as "
        f"@e[type=minecraft:armor_stand,tag=fc_fork_order,sort={sort},limit=2] "
        f"run scoreboard players operation #fork_order_acc {objective} >< @s {objective}"
    )


def run_fork_order_fixture(client: RconClient, mode: str) -> dict[str, object]:
    objective = "fc_fork_order"
    client.command(f"scoreboard objectives add {objective} dummy")
    client.command("forceload add 32 0")
    client.command("kill @e[type=minecraft:armor_stand,tag=fc_fork_order]")
    for index, (position, actor_tag, value) in enumerate(
        (
            ("32.5 100 0.5", "fc_fork_order_a", 2),
            ("33.5 100 0.5", "fc_fork_order_b", 3),
            ("34.5 100 0.5", "fc_fork_order_c", 5),
        )
    ):
        response = client.command(
            f'summon minecraft:armor_stand {position} '
            f'{{NoGravity:1b,Invisible:1b,Invulnerable:1b,Tags:["fc_fork_order","{actor_tag}"]}}'
        )
        if "summoned" not in response.casefold():
            raise RuntimeError(f"{mode} could not summon fork-order actor {index}: {response!r}")
        client.command(f"scoreboard players set @e[tag={actor_tag}] {objective} {value}")

    observations: list[dict[str, object]] = []
    for fork_limit in (1, 2, 3, 4):
        client.command(f"gamerule minecraft:max_command_forks {fork_limit}")
        client.command(f"gamerule {LEVEL} 64")
        for actor_tag, value in (
            ("fc_fork_order_a", 2),
            ("fc_fork_order_b", 3),
            ("fc_fork_order_c", 5),
        ):
            client.command(f"scoreboard players set @e[tag={actor_tag}] {objective} {value}")
        client.command(f"scoreboard players set #fork_order_acc {objective} 7")
        direct_response = client.command(
            "execute positioned 32 100 0 as "
            "@e[type=minecraft:armor_stand,tag=fc_fork_order,sort=nearest,limit=2] "
            f"run scoreboard players operation #fork_order_acc {objective} >< @s {objective}"
        )
        direct_scores = {
            holder: read_score(client, holder, objective)
            for holder in (
                "#fork_order_acc",
                "@e[tag=fc_fork_order_a,limit=1]",
                "@e[tag=fc_fork_order_b,limit=1]",
                "@e[tag=fc_fork_order_c,limit=1]",
            )
        }
        for actor_tag, value in (
            ("fc_fork_order_a", 2),
            ("fc_fork_order_b", 3),
            ("fc_fork_order_c", 5),
        ):
            client.command(f"scoreboard players set @e[tag={actor_tag}] {objective} {value}")
        client.command(f"scoreboard players set #fork_order_acc {objective} 7")
        function_response = client.command(
            "function function_compiler_probe:quota_fork_order"
        )
        scores = {
            holder: read_score(client, holder, objective)
            for holder in (
                "#fork_order_acc",
                "@e[tag=fc_fork_order_a,limit=1]",
                "@e[tag=fc_fork_order_b,limit=1]",
                "@e[tag=fc_fork_order_c,limit=1]",
            )
        }
        expected_scores = (
            {
                "#fork_order_acc": 7,
                "@e[tag=fc_fork_order_a,limit=1]": 2,
                "@e[tag=fc_fork_order_b,limit=1]": 3,
                "@e[tag=fc_fork_order_c,limit=1]": 5,
            }
            if fork_limit < 3
            else {
                "#fork_order_acc": 3,
                "@e[tag=fc_fork_order_a,limit=1]": 7,
                "@e[tag=fc_fork_order_b,limit=1]": 2,
                "@e[tag=fc_fork_order_c,limit=1]": 5,
            }
        )
        if scores != expected_scores:
            raise RuntimeError(
                f"{mode} nearest-first fork state at limit {fork_limit} was "
                f"{scores!r}; expected {expected_scores!r}"
            )
        if fork_limit == 1 and "maximum number of contexts (1) reached" not in direct_response.casefold():
            raise RuntimeError(
                f"{mode} direct nearest fork overflow at cap 1 returned "
                f"{direct_response!r}; expected the maximum-context error"
            )
        if fork_limit == 2 and direct_response:
            raise RuntimeError(
                f"{mode} direct nearest fork at cap 2 returned unexpected "
                f"feedback: {direct_response!r}"
            )
        observations.append(
            {
                "max_command_forks": fork_limit,
                "direct_execute_response": direct_response,
                "direct_scores_after": direct_scores,
                "function_response": function_response,
                "scores_after": scores,
            }
        )

    furthest_observations: list[dict[str, object]] = []
    for fork_limit in (1, 2, 3, 4):
        client.command(f"gamerule minecraft:max_command_forks {fork_limit}")
        client.command(f"gamerule {LEVEL} 64")
        for actor_tag, value in (
            ("fc_fork_order_a", 2),
            ("fc_fork_order_b", 3),
            ("fc_fork_order_c", 5),
        ):
            client.command(f"scoreboard players set @e[tag={actor_tag}] {objective} {value}")
        client.command(f"scoreboard players set #fork_order_acc {objective} 7")
        direct_response = client.command(
            "execute positioned 32 100 0 as "
            "@e[type=minecraft:armor_stand,tag=fc_fork_order,sort=furthest,limit=2] "
            f"run scoreboard players operation #fork_order_acc {objective} >< @s {objective}"
        )
        direct_scores = {
            holder: read_score(client, holder, objective)
            for holder in (
                "#fork_order_acc",
                "@e[tag=fc_fork_order_a,limit=1]",
                "@e[tag=fc_fork_order_b,limit=1]",
                "@e[tag=fc_fork_order_c,limit=1]",
            )
        }
        for actor_tag, value in (
            ("fc_fork_order_a", 2),
            ("fc_fork_order_b", 3),
            ("fc_fork_order_c", 5),
        ):
            client.command(f"scoreboard players set @e[tag={actor_tag}] {objective} {value}")
        client.command(f"scoreboard players set #fork_order_acc {objective} 7")
        function_response = client.command(
            "function function_compiler_probe:quota_fork_order_furthest"
        )
        scores = {
            holder: read_score(client, holder, objective)
            for holder in (
                "#fork_order_acc",
                "@e[tag=fc_fork_order_a,limit=1]",
                "@e[tag=fc_fork_order_b,limit=1]",
                "@e[tag=fc_fork_order_c,limit=1]",
            )
        }
        expected_scores = (
            {
                "#fork_order_acc": 7,
                "@e[tag=fc_fork_order_a,limit=1]": 2,
                "@e[tag=fc_fork_order_b,limit=1]": 3,
                "@e[tag=fc_fork_order_c,limit=1]": 5,
            }
            if fork_limit < 3
            else {
                "#fork_order_acc": 3,
                "@e[tag=fc_fork_order_a,limit=1]": 2,
                "@e[tag=fc_fork_order_b,limit=1]": 5,
                "@e[tag=fc_fork_order_c,limit=1]": 7,
            }
        )
        if direct_scores != expected_scores or scores != expected_scores:
            raise RuntimeError(
                f"{mode} furthest-first fork state at limit {fork_limit} was "
                f"direct={direct_scores!r}, function={scores!r}; "
                f"expected {expected_scores!r}"
            )
        if fork_limit == 1 and "maximum number of contexts (1) reached" not in direct_response.casefold():
            raise RuntimeError(
                f"{mode} direct furthest fork overflow at cap 1 returned "
                f"{direct_response!r}; expected the maximum-context error"
            )
        if fork_limit == 2 and direct_response:
            raise RuntimeError(
                f"{mode} direct furthest fork at cap 2 returned unexpected "
                f"feedback: {direct_response!r}"
            )
        furthest_observations.append(
            {
                "max_command_forks": fork_limit,
                "direct_execute_response": direct_response,
                "direct_scores_after": direct_scores,
                "function_response": function_response,
                "scores_after": scores,
            }
        )

    sort_summary: dict[str, dict[str, object]] = {}
    client.command("gamerule minecraft:max_command_forks 64")
    client.command(f"gamerule {LEVEL} 64")
    for sort in ("random", "arbitrary"):
        client.command(f"scoreboard players set #fork_order_count {objective} 0")
        direct_response = client.command(
            "execute positioned 32 100 0 as "
            f"@e[type=minecraft:armor_stand,tag=fc_fork_order,sort={sort}] "
            f"run scoreboard players add #fork_order_count {objective} 1"
        )
        direct_count = read_score(client, "#fork_order_count", objective)
        client.command(f"scoreboard players set #fork_order_count {objective} 0")
        function_response = client.command(
            f"function function_compiler_probe:quota_fork_order_{sort}"
        )
        function_count = read_score(client, "#fork_order_count", objective)
        if direct_count != 3 or function_count != 3:
            raise RuntimeError(
                f"{mode} {sort} fork selection visited {direct_count} direct and "
                f"{function_count} function actors; expected 3 each"
            )
        sort_summary[sort] = {
            "direct_execute_response": direct_response,
            "direct_actor_count": direct_count,
            "function_response": function_response,
            "function_actor_count": function_count,
        }

        low_cap_cases: list[dict[str, object]] = []
        for fork_limit in (1, 2, 3, 4):
            client.command(f"gamerule minecraft:max_command_forks {fork_limit}")
            client.command(f"gamerule {LEVEL} 64")
            actor_holders = (
                "@e[tag=fc_fork_order_a,limit=1]",
                "@e[tag=fc_fork_order_b,limit=1]",
                "@e[tag=fc_fork_order_c,limit=1]",
            )
            for holder in (*actor_holders, "#fork_order_followup"):
                client.command(f"scoreboard players set {holder} {objective} 0")

            direct_response = client.command(
                "execute positioned 32 100 0 as "
                f"@e[type=minecraft:armor_stand,tag=fc_fork_order,"
                f"sort={sort},limit=2] run scoreboard players add @s {objective} 1"
            )
            direct_actor_scores = [
                read_score(client, holder, objective) for holder in actor_holders
            ]
            direct_branch_count = sum(direct_actor_scores)
            direct_selected_count = sum(value != 0 for value in direct_actor_scores)

            for holder in (*actor_holders, "#fork_order_followup"):
                client.command(f"scoreboard players set {holder} {objective} 0")
            client.command(
                f"function function_compiler_probe:quota_fork_order_{sort}_resume"
            )
            function_actor_scores = [
                read_score(client, holder, objective) for holder in actor_holders
            ]
            function_branch_count = sum(function_actor_scores)
            function_selected_count = sum(value != 0 for value in function_actor_scores)
            function_followup = read_score(client, "#fork_order_followup", objective)

            expected_branch_count = 0 if fork_limit < 3 else 2
            if direct_branch_count != expected_branch_count:
                raise RuntimeError(
                    f"{mode} {sort} direct fork at cap {fork_limit} executed "
                    f"{direct_branch_count} branches; expected {expected_branch_count}"
                )
            if function_branch_count != expected_branch_count:
                raise RuntimeError(
                    f"{mode} {sort} function fork at cap {fork_limit} executed "
                    f"{function_branch_count} branches; expected {expected_branch_count}"
                )
            if direct_selected_count != expected_branch_count:
                raise RuntimeError(
                    f"{mode} {sort} direct fork at cap {fork_limit} changed "
                    f"{direct_selected_count} actors; expected {expected_branch_count}"
                )
            if function_selected_count != expected_branch_count:
                raise RuntimeError(
                    f"{mode} {sort} function fork at cap {fork_limit} changed "
                    f"{function_selected_count} actors; expected {expected_branch_count}"
                )
            if function_followup != 10:
                raise RuntimeError(
                    f"{mode} {sort} function fork at cap {fork_limit} left its "
                    f"follow-up at {function_followup}; expected 10"
                )
            overflow_reported = (
                "maximum number of contexts (1) reached" in direct_response.casefold()
            )
            no_feedback = direct_response == ""
            if fork_limit == 1 and not overflow_reported:
                raise RuntimeError(
                    f"{mode} {sort} direct fork overflow at cap 1 returned "
                    f"{direct_response!r}; expected the maximum-context error"
                )
            if fork_limit == 2 and not no_feedback:
                raise RuntimeError(
                    f"{mode} {sort} direct fork at cap 2 returned unexpected "
                    f"feedback: {direct_response!r}"
                )
            low_cap_cases.append(
                {
                    "max_command_forks": fork_limit,
                    "direct_branch_count": direct_branch_count,
                    "direct_selected_actor_count": direct_selected_count,
                    "direct_overflow_reported": overflow_reported,
                    "direct_no_feedback": no_feedback,
                    "function_branch_count": function_branch_count,
                    "function_selected_actor_count": function_selected_count,
                    "function_followup": function_followup,
                }
            )
        sort_summary[sort]["low_cap_cases"] = low_cap_cases

        # MO-09: identity ordering for the unordered sorts. Measured on the
        # pinned vanilla 26.3 server: sort=arbitrary resolves candidates in
        # entity insertion (summon) order - (a, b) for the canonical summon
        # sequence - and that order is stable across repeated invocations,
        # /reload, a server restart on the same world, and fresh worlds with
        # different seeds, so it is oracle-able exactly. sort=random is
        # non-deterministic by design (24 direct trials covered all three
        # candidate pairs uniformly, every trial exactly two distinct
        # actors), so only per-trial set semantics are asserted, plus a
        # distinct-pair floor across trials proving the selection is delegated
        # to vanilla's randomness rather than pinned by the fork. Both paths
        # must also re-resolve candidates per execution: killing a selected
        # actor must change the next invocation's selection.
        client.command("gamerule minecraft:max_command_forks 64")
        client.command(f"gamerule {LEVEL} 64")
        actor_tags = tuple(FORK_ORDER_ACTOR_VALUES)
        live_candidates = frozenset(actor_tags)
        if sort == "arbitrary":
            expected_order = ("fc_fork_order_a", "fc_fork_order_b")
            identity_orders: list[tuple[str, str]] = []
            for _ in range(5):
                reset_fork_order_actors(client, objective, actor_tags)
                fork_order_identity_swap(client, objective, sort)
                identity_orders.append(decode_fork_order(client, objective, actor_tags))
            function_identity_orders: list[tuple[str, str]] = []
            for _ in range(5):
                reset_fork_order_actors(client, objective, actor_tags)
                client.command(
                    f"function function_compiler_probe:mo09_fork_{sort}_identity"
                )
                function_identity_orders.append(
                    decode_fork_order(client, objective, actor_tags)
                )
            if set(identity_orders) != {expected_order}:
                raise RuntimeError(
                    f"{mode} {sort} fork identity order was {identity_orders!r}; "
                    f"expected only {expected_order!r}"
                )
            if set(function_identity_orders) != {expected_order}:
                raise RuntimeError(
                    f"{mode} {sort} function fork identity order was "
                    f"{function_identity_orders!r}; expected only {expected_order!r}"
                )
            # Cap sweep for the order-sensitive swap: the cap includes the
            # parent context, so a limit=2 selector needs cap >= 3 to fork
            # both branches. Cap 1 reports the maximum-context error and cap 2
            # truncates silently; both leave the state untouched.
            cap_cases: list[dict[str, object]] = []
            for fork_limit in (1, 2, 3, 4):
                client.command(f"gamerule minecraft:max_command_forks {fork_limit}")
                client.command(f"gamerule {LEVEL} 64")
                reset_fork_order_actors(client, objective, actor_tags)
                direct_response = fork_order_identity_swap(client, objective, sort)
                direct_scores = read_fork_order_scores(client, objective, actor_tags)
                direct_order = (
                    decode_fork_order(client, objective, actor_tags)
                    if fork_limit >= 3
                    else None
                )
                reset_fork_order_actors(client, objective, actor_tags)
                client.command(
                    f"function function_compiler_probe:mo09_fork_{sort}_identity"
                )
                function_scores = read_fork_order_scores(client, objective, actor_tags)
                function_order = (
                    decode_fork_order(client, objective, actor_tags)
                    if fork_limit >= 3
                    else None
                )
                if fork_limit < 3:
                    untouched = {
                        tag: FORK_ORDER_ACTOR_VALUES[tag] for tag in actor_tags
                    }
                    if direct_scores != untouched or function_scores != untouched:
                        raise RuntimeError(
                            f"{mode} {sort} fork at cap {fork_limit} executed "
                            f"branches despite the cap: direct={direct_scores!r}, "
                            f"function={function_scores!r}"
                        )
                    overflow_reported = (
                        "maximum number of contexts (1) reached"
                        in direct_response.casefold()
                    )
                    if fork_limit == 1 and not overflow_reported:
                        raise RuntimeError(
                            f"{mode} {sort} direct fork overflow at cap 1 "
                            f"returned {direct_response!r}; expected the "
                            "maximum-context error"
                        )
                    if fork_limit == 2 and direct_response:
                        raise RuntimeError(
                            f"{mode} {sort} direct fork at cap 2 returned "
                            f"unexpected feedback: {direct_response!r}"
                        )
                else:
                    if direct_order != expected_order:
                        raise RuntimeError(
                            f"{mode} {sort} fork order at cap {fork_limit} was "
                            f"{direct_order!r}; expected {expected_order!r}"
                        )
                    if function_order != expected_order:
                        raise RuntimeError(
                            f"{mode} {sort} function fork order at cap "
                            f"{fork_limit} was {function_order!r}; expected "
                            f"{expected_order!r}"
                        )
                cap_cases.append(
                    {
                        "max_command_forks": fork_limit,
                        "direct_overflow_reported": (
                            "maximum number of contexts (1) reached"
                            in direct_response.casefold()
                        ),
                    }
                )
            client.command("gamerule minecraft:max_command_forks 64")
            client.command(f"gamerule {LEVEL} 64")
            sort_summary[sort]["identity_cases"] = {
                "trial_count": len(identity_orders),
                "identity_order": list(expected_order),
                "cap_cases": cap_cases,
            }
        else:
            direct_pairs: set[frozenset[str]] = set()
            function_pairs: set[frozenset[str]] = set()
            for _ in range(16):
                reset_fork_order_actors(client, objective, actor_tags)
                fork_order_identity_swap(client, objective, sort)
                direct_pairs.add(
                    frozenset(decode_fork_order(client, objective, actor_tags))
                )
                reset_fork_order_actors(client, objective, actor_tags)
                client.command(
                    f"function function_compiler_probe:mo09_fork_{sort}_identity"
                )
                function_pairs.add(
                    frozenset(decode_fork_order(client, objective, actor_tags))
                )
            for pairs, label in (
                (direct_pairs, "direct"),
                (function_pairs, "function"),
            ):
                if len(pairs) < 2:
                    raise RuntimeError(
                        f"{mode} {sort} {label} fork saw {len(pairs)} distinct "
                        "candidate pair across 16 trials; expected vanilla's "
                        "randomness to produce at least 2"
                    )
            sort_summary[sort]["identity_cases"] = {
                "trial_count": 16,
                "multiple_pairs_observed": True,
            }
        # Candidate-list freshness: killing a selected actor must change the
        # next invocation's selection on both paths. With b dead the
        # remaining candidates are a and c, so the arbitrary order is exact
        # and the random pair set is deterministic.
        client.command("kill @e[type=minecraft:armor_stand,tag=fc_fork_order_b]")
        post_kill_tags = ("fc_fork_order_a", "fc_fork_order_c")
        reset_fork_order_actors(client, objective, post_kill_tags)
        fork_order_identity_swap(client, objective, sort)
        direct_post_kill = decode_fork_order(client, objective, post_kill_tags)
        reset_fork_order_actors(client, objective, post_kill_tags)
        client.command(f"function function_compiler_probe:mo09_fork_{sort}_identity")
        function_post_kill = decode_fork_order(client, objective, post_kill_tags)
        expected_post_kill = ("fc_fork_order_a", "fc_fork_order_c")
        if sort == "arbitrary":
            if direct_post_kill != expected_post_kill:
                raise RuntimeError(
                    f"{mode} {sort} fork did not re-resolve after killing a "
                    f"selected actor: {direct_post_kill!r}"
                )
            if function_post_kill != expected_post_kill:
                raise RuntimeError(
                    f"{mode} {sort} function fork did not re-resolve after "
                    f"killing a selected actor: {function_post_kill!r}"
                )
        else:
            expected_post_kill_pair = frozenset(expected_post_kill)
            if frozenset(direct_post_kill) != expected_post_kill_pair:
                raise RuntimeError(
                    f"{mode} {sort} fork did not re-resolve after killing a "
                    f"selected actor: {direct_post_kill!r}"
                )
            if frozenset(function_post_kill) != expected_post_kill_pair:
                raise RuntimeError(
                    f"{mode} {sort} function fork did not re-resolve after "
                    f"killing a selected actor: {function_post_kill!r}"
                )
        sort_summary[sort]["identity_cases"]["post_kill_order"] = sorted(
            direct_post_kill
        )
        # Restore the canonical actor set so later sections and fixtures see
        # the three actors in summon order a, b, c. For arbitrary the restore
        # is verified by one direct swap; for random it is verified
        # transitively by the arbitrary iteration that follows.
        client.command("kill @e[type=minecraft:armor_stand,tag=fc_fork_order]")
        for tag in actor_tags:
            response = client.command(
                "summon minecraft:armor_stand "
                f"{FORK_ORDER_ACTOR_POSITIONS[tag]} "
                f'{{NoGravity:1b,Invisible:1b,Invulnerable:1b,'
                f'Tags:["fc_fork_order","{tag}"]}}'
            )
            if "summoned" not in response.casefold():
                raise RuntimeError(
                    f"{mode} could not re-summon fork-order actor {tag}: {response!r}"
                )
        reset_fork_order_actors(client, objective, actor_tags)
        if sort == "arbitrary":
            reset_fork_order_actors(client, objective, actor_tags)
            fork_order_identity_swap(client, objective, sort)
            restored_order = decode_fork_order(client, objective, actor_tags)
            if restored_order != expected_order:
                raise RuntimeError(
                    f"{mode} {sort} fork order after the actor restore was "
                    f"{restored_order!r}; expected {expected_order!r}"
                )

    client.command("gamerule minecraft:max_command_forks 65536")
    client.command(f"gamerule {LEVEL} 65536")
    return {
        "ordered_fork_cases": observations,
        "furthest_fork_cases": furthest_observations,
        "unordered_sort_cases": sort_summary,
    }


def run_mode(
    mode: str,
    packet_ids: PacketIds,
    reload_cycles: int = 5,
    whole_reload_failure_probe: bool = False,
    concurrent_reload_probe: bool = False,
    callback_metric_probe: bool = False,
) -> dict[str, object]:
    lifecycle_pack_root = prepare_server_files()
    failure_marker = RUN_DIR / "resource-reload-failure.trigger"
    failure_armed = failure_marker.with_name(failure_marker.name + ".armed")
    failure_observed = failure_marker.with_name(failure_marker.name + ".observed")
    for marker_path in (failure_marker, failure_armed, failure_observed):
        marker_path.unlink(missing_ok=True)
    concurrent_marker = RUN_DIR / "resource-reload-concurrent.trigger"
    concurrent_armed = concurrent_marker.with_name(concurrent_marker.name + ".armed")
    concurrent_entered = concurrent_marker.with_name(concurrent_marker.name + ".entered")
    concurrent_release = concurrent_marker.with_name(concurrent_marker.name + ".release")
    for marker_path in (
        concurrent_marker,
        concurrent_armed,
        concurrent_entered,
        concurrent_release,
    ):
        marker_path.unlink(missing_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = REPORT_DIR / f"{mode}.server.log"
    process, log_handle = start_server(
        mode,
        log_path,
        whole_reload_failure_probe=whole_reload_failure_probe,
        concurrent_reload_probe=concurrent_reload_probe,
        callback_metric_probe=callback_metric_probe,
    )
    client: RconClient | None = None
    bot: PlayerBot | None = None
    try:
        client = wait_for_rcon(process)
        if whole_reload_failure_probe:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not failure_armed.is_file():
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{mode} stopped before arming the whole-reload failure probe"
                    )
                time.sleep(0.1)
            if not failure_armed.is_file():
                raise RuntimeError(
                    f"{mode} test-only reload failure mod did not arm: {failure_armed}"
                )
        if concurrent_reload_probe:
            deadline = time.monotonic() + 30
            while time.monotonic() < deadline and not concurrent_armed.is_file():
                if process.poll() is not None:
                    raise RuntimeError(
                        f"{mode} stopped before arming the concurrent reload probe"
                    )
                time.sleep(0.1)
            if not concurrent_armed.is_file():
                raise RuntimeError(
                    f"{mode} test-only concurrent reload probe did not arm: "
                    f"{concurrent_armed}"
                )
        bot = connect_probe_player(packet_ids, client, mode)
        objective_response = client.command(f"scoreboard objectives add {OBJECTIVE} dummy")
        if "Unknown" in objective_response or "Incorrect" in objective_response:
            raise RuntimeError(f"Could not create probe objective: {objective_response!r}")
        lifecycle_initial = initialize_lifecycle_pack(client, mode)
        status = client.command("function_compiler_probe status")
        if "FC_PROBE present=true" not in status:
            raise RuntimeError(f"Probe function did not load. RCON status: {status!r}")
        parse_match = re.search(r"probe_function_parses=(\d+)", status)
        if parse_match is None or int(parse_match.group(1)) < 1:
            raise RuntimeError(
                "Expected the probe function to be parsed during startup reload; "
                f"status={status!r}"
            )
        initial_parse_count = int(parse_match.group(1))

        expected_wrapped = callback_metric_probe or mode in {
            "wrapper-on", "score-add-on", "instrument-only", "score-add-timed",
            "fused-interpreted", "bytecode-emitted", "bytecode-compile-failure",
            "selective-macro-arguments",
        }
        expected_status = f"wrapped={str(expected_wrapped).lower()}"
        if expected_status not in status:
            raise RuntimeError(f"Expected {expected_status} in probe status: {status!r}")
        expected_prototype = mode in {
            "score-add-on", "score-add-timed", "fused-interpreted", "bytecode-emitted",
            "bytecode-compile-failure",
        }
        if f"score_add_prototype_enabled={str(expected_prototype).lower()}" not in status:
            raise RuntimeError(
                f"Expected score_add_prototype_enabled={expected_prototype} in status: {status!r}"
            )
        expected_timing = mode in {"instrument-only", "score-add-timed"}
        if f"score_add_timing_enabled={str(expected_timing).lower()}" not in status:
            raise RuntimeError(
                f"Expected score_add_timing_enabled={expected_timing} in status: {status!r}"
            )
        expected_delegate = mode not in {"fused-interpreted", "bytecode-emitted"}
        for invariant in (
            "tag_same_instance=true",
            f"delegates_original={str(expected_delegate).lower()}",
            "original_fallback_retained=true",
            f"fused_region_prototype_enabled={str(mode == 'fused-interpreted').lower()}",
            f"bytecode_region_prototype_enabled={str(mode in {'bytecode-emitted', 'bytecode-compile-failure'}).lower()}",
            f"bytecode_compile_failure_forced={str(mode == 'bytecode-compile-failure').lower()}",
        ):
            if invariant not in status:
                raise RuntimeError(f"Expected {invariant} in probe status: {status!r}")
        expected_lifecycle_status = {
            "lifecycle_probe_wrapped": expected_wrapped,
            "lifecycle_probe_v2_wrapped": expected_wrapped,
            "lifecycle_tag_has_probe": True,
            "lifecycle_tag_same_probe_instance": True,
            "lifecycle_tag_has_probe_v2": False,
            "lifecycle_tag_same_probe_v2_instance": False,
            "lifecycle_macro_is_macro": True,
            "lifecycle_macro_wrapped": callback_metric_probe or mode in MACRO_WRAPPER_MODES,
        }
        for key, expected in expected_lifecycle_status.items():
            if f"{key}={str(expected).lower()}" not in status:
                raise RuntimeError(
                    f"{mode} initial lifecycle status expected {key}={expected}: {status!r}"
                )

        prepare_modifier_actors(client, mode)

        scores: dict[int, int] = {}
        command_responses: list[dict[str, object]] = []
        for quota in QUOTAS:
            game_rule_response = client.command(f"gamerule {LEVEL} {quota}")
            if str(quota) not in game_rule_response:
                raise RuntimeError(f"Could not set quota to {quota}: {game_rule_response!r}")
            client.command(f"scoreboard players set {HOLDER} {OBJECTIVE} 0")
            run_response = client.command("function_compiler_probe run")
            score_response = client.command(f"scoreboard players get {HOLDER} {OBJECTIVE}")
            match = re.search(r"has (-?\d+)", score_response)
            if match is None:
                raise RuntimeError(f"Could not parse quota {quota} score: {score_response!r}")
            scores[quota] = int(match.group(1))
            command_responses.append(
                {
                    "quota": quota,
                    "gamerule": game_rule_response,
                    "run": run_response,
                    "score": score_response,
                }
            )

        direct_fixtures = run_direct_function_fixtures(client, mode)
        fork_limit_fixture = run_fork_limit_fixture(client, mode)
        fork_order_fixture = run_fork_order_fixture(client, mode)
        scoreboard_semantics = run_scoreboard_semantics(client, mode)
        delegation_contract = run_delegation_contract(client, mode)
        control_flow_fallback_cases = run_control_flow_fallback_cases(
            client, mode, RUN_DIR
        )
        callback_metric_fixture = run_command_callback_metrics_fixture(
            client, mode, measure_callbacks=callback_metric_probe
        )
        post_execution_status = client.command("function_compiler_probe status")
        score_add_compiled_match = re.search(r"score_add_compiled=(\d+)", post_execution_status)
        score_add_executed_match = re.search(r"score_add_executed=(\d+)", post_execution_status)
        if score_add_compiled_match is None or score_add_executed_match is None:
            raise RuntimeError(f"{mode} status omitted ScoreAdd prototype counters")
        score_add_metrics = {
            "compiled": int(score_add_compiled_match.group(1)),
            "executed": int(score_add_executed_match.group(1)),
        }
        score_add_timed_calls_match = re.search(
            r"score_add_timed_calls=(\d+)", post_execution_status
        )
        score_add_elapsed_match = re.search(
            r"score_add_elapsed_nanos=(\d+)", post_execution_status
        )
        if score_add_timed_calls_match is None or score_add_elapsed_match is None:
            raise RuntimeError(f"{mode} status omitted ScoreAdd timing counters")
        score_add_timing = {
            "timed_calls": int(score_add_timed_calls_match.group(1)),
            "elapsed_nanos": int(score_add_elapsed_match.group(1)),
        }
        if expected_timing and score_add_timing["timed_calls"] == 0:
            raise RuntimeError(f"{mode} enabled timing but recorded no callbacks")
        if not expected_timing and score_add_timing["timed_calls"] != 0:
            raise RuntimeError(f"{mode} recorded callbacks while timing was disabled")
        if expected_prototype and min(score_add_metrics.values()) < 1:
            raise RuntimeError(
                f"{mode} prototype did not compile and execute a ScoreAdd command: "
                f"{score_add_metrics!r}"
            )
        if not expected_prototype and score_add_metrics["executed"] != 0:
            raise RuntimeError(
                f"{mode} unexpectedly executed a ScoreAdd prototype: {score_add_metrics!r}"
            )
        # MO-02's fixtures each contain exactly two `execute store ... storage`
        # lines, and the dedicated counter increments once per compiled
        # DataStore modifier. Score parity alone cannot prove specialization: a
        # fallback executes the same vanilla commands. A function is compiled
        # in every arm whose configuration motivates compilation (ScoreAdd
        # prototype, timing instrumentation, fused, or bytecode), which is a
        # superset of expected_prototype, so this assertion keys on the same
        # disjunction the wrapper compiles under. Reloads may recompile a
        # function, so a compiling arm is asserted as a lower bound and every
        # other arm as zero.
        mo02_expected_compiled = expected_prototype or expected_timing
        mo02_compiled: dict[str, int] = {}
        for fixture, key in (
            ("mo02_store_result", "data_store_compiled_mo02_result"),
            ("mo02_store_failures", "data_store_compiled_mo02_failures"),
        ):
            match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)", post_execution_status)
            if match is None:
                raise RuntimeError(f"{mode} status omitted {key}")
            mo02_compiled[fixture] = int(match.group(1))
        for fixture, compiled in mo02_compiled.items():
            if mo02_expected_compiled and compiled < 2:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} DataStore lines; "
                    f"expected at least 2"
                )
            if not mo02_expected_compiled and compiled != 0:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} DataStore lines in a "
                    f"non-specializing arm"
                )
        data_store_metrics = {
            "expected_minimum_per_fixture": 2 if mo02_expected_compiled else 0,
            "compiled_by_fixture": mo02_compiled,
        }
        # ST-02's fixtures have three and four store-chained bossbar lines
        # respectively, and the dedicated counter increments once per compiled
        # wrap event - twice per chained line per generation, the same
        # per-line doubling the DataStore counters show (two MO-02 lines read
        # 4). Bare bossbar lines are not in the EXECUTE-stage parser list, so
        # they stay on the vanilla path like every other state-machine family
        # outside tag/teleport/kill; the lower bound therefore keys on the
        # chain counts. Score parity alone cannot prove bossbar
        # specialization: the fallback runs the same vanilla commands. The
        # same disjunction as the DataStore assertion applies (a function is
        # compiled in every arm whose configuration motivates compilation),
        # reloads recompile, so compiling arms get a per-fixture lower bound
        # and every other arm zero.
        st02_expected_compiled = expected_prototype or expected_timing
        st02_minimums = {"st02_bossbar_ops": 3, "st02_bossbar_values": 4}
        st02_compiled: dict[str, int] = {}
        for fixture, key in (
            ("st02_bossbar_ops", "bossbar_compiled_st02_bossbar_ops"),
            ("st02_bossbar_values", "bossbar_compiled_st02_bossbar_values"),
        ):
            match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)", post_execution_status)
            if match is None:
                raise RuntimeError(f"{mode} status omitted {key}")
            st02_compiled[fixture] = int(match.group(1))
        for fixture, compiled in st02_compiled.items():
            if st02_expected_compiled and compiled < st02_minimums[fixture]:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} bossbar lines; "
                    f"expected at least {st02_minimums[fixture]}"
                )
            if not st02_expected_compiled and compiled != 0:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} bossbar lines in a "
                    f"non-specializing arm"
                )
        bossbar_metrics = {
            "expected_minimum_per_fixture": (
                st02_minimums if st02_expected_compiled
                else {fixture: 0 for fixture in st02_minimums}
            ),
            "compiled_by_fixture": st02_compiled,
        }
        # ST-06's modify-half fixture has one store-chained item modify line,
        # and the dedicated counter increments once per compiled wrap event -
        # twice per chained line per generation, the same per-line doubling
        # the DataStore and bossbar counters show. Bare item lines are not in
        # the EXECUTE-stage parser list, so they stay on the vanilla path;
        # the fixture's `execute if items` conditions go through
        # ItemPredicateParser and do not increment this counter. Score parity
        # alone cannot prove item-command specialization: the fallback runs
        # the same vanilla commands. The same disjunction as the DataStore
        # assertion applies, reloads recompile, so compiling arms get a
        # lower bound and every other arm zero.
        st06_expected_compiled = expected_prototype or expected_timing
        st06_minimums = {"st06_item_modify": 1}
        st06_compiled: dict[str, int] = {}
        for fixture, key in (
            ("st06_item_modify", "item_command_compiled_st06_item_modify"),
        ):
            match = re.search(rf"(?:^|\s){re.escape(key)}=(\d+)", post_execution_status)
            if match is None:
                raise RuntimeError(f"{mode} status omitted {key}")
            st06_compiled[fixture] = int(match.group(1))
        for fixture, compiled in st06_compiled.items():
            if st06_expected_compiled and compiled < st06_minimums[fixture]:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} item command lines; "
                    f"expected at least {st06_minimums[fixture]}"
                )
            if not st06_expected_compiled and compiled != 0:
                raise RuntimeError(
                    f"{mode} {fixture} compiled {compiled} item command lines in a "
                    f"non-specializing arm"
                )
        item_command_metrics = {
            "expected_minimum_per_fixture": (
                st06_minimums if st06_expected_compiled
                else {fixture: 0 for fixture in st06_minimums}
            ),
            "compiled_by_fixture": st06_compiled,
        }
        fused_compiled_match = re.search(r"fused_regions_compiled=(\d+)", post_execution_status)
        fused_executed_match = re.search(r"fused_regions_executed=(\d+)", post_execution_status)
        if fused_compiled_match is None or fused_executed_match is None:
            raise RuntimeError(f"{mode} status omitted fused-region counters")
        fused_region_metrics = {
            "compiled": int(fused_compiled_match.group(1)),
            "executed": int(fused_executed_match.group(1)),
        }
        if mode == "fused-interpreted" and min(fused_region_metrics.values()) < 1:
            raise RuntimeError(
                f"{mode} did not compile and execute a fused region: {fused_region_metrics!r}"
            )
        if mode != "fused-interpreted" and any(fused_region_metrics.values()):
            raise RuntimeError(
                f"{mode} unexpectedly ran a fused region: {fused_region_metrics!r}"
            )
        bytecode_region_metrics = {
            "compiled": status_counter(post_execution_status, "bytecode_regions_compiled"),
            "compile_failed": status_counter(post_execution_status, "bytecode_regions_compile_failed"),
            "executed": status_counter(post_execution_status, "bytecode_regions_executed"),
        }
        if (
            mode != "bytecode-compile-failure"
            and bytecode_region_metrics["compile_failed"] != 0
        ):
            raise RuntimeError(
                f"{mode} had bytecode region compilation failures: {bytecode_region_metrics!r}"
            )
        if mode == "bytecode-emitted" and min(
            bytecode_region_metrics["compiled"], bytecode_region_metrics["executed"]
        ) < 1:
            raise RuntimeError(
                f"{mode} did not compile and execute a bytecode region: {bytecode_region_metrics!r}"
            )
        if mode == "bytecode-compile-failure" and (
            bytecode_region_metrics["compile_failed"] < 1
            or bytecode_region_metrics["compiled"] != 0
            or bytecode_region_metrics["executed"] != 0
        ):
            raise RuntimeError(
                f"{mode} did not fall back after forced compile failure: "
                f"{bytecode_region_metrics!r}"
            )
        if mode not in {"bytecode-emitted", "bytecode-compile-failure"} and any(
            bytecode_region_metrics.values()
        ):
            raise RuntimeError(
                f"{mode} unexpectedly ran a bytecode region: {bytecode_region_metrics!r}"
            )
        post_execution_parse_match = re.search(
            r"probe_function_parses=(\d+)", post_execution_status
        )
        if (
            post_execution_parse_match is None
            or int(post_execution_parse_match.group(1)) != initial_parse_count
        ):
            raise RuntimeError(
                f"{mode} reparsed quota_three during steady-state invocation: "
                f"initial={initial_parse_count}, status={post_execution_status!r}"
            )

        lifecycle_functions = run_lifecycle_functions(client, mode)
        lifecycle_reloads = reload_lifecycle_pack(
            client,
            mode,
            lifecycle_pack_root,
            reload_cycles=reload_cycles,
            whole_reload_failure_probe=whole_reload_failure_probe,
            concurrent_reload_probe=concurrent_reload_probe,
            callback_metric_probe=callback_metric_probe,
        )
        debug_traces = [
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:quota_three",
                expected_score=3,
                expected_command_events=3,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:score_add_literal",
                expected_score=7,
                expected_command_events=1,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_missing_objective",
                expected_score=22,
                expected_command_events=6,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_result_fail_outer",
                expected_score=32,
                expected_command_events=6,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_success_return_value_outer",
                expected_score=32,
                expected_command_events=6,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_result_nested_return_outer",
                expected_score=37,
                expected_command_events=8,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_success_nested_return_outer",
                expected_score=37,
                expected_command_events=8,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_success_nested_fail_outer",
                expected_score=37,
                expected_command_events=8,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_result_discard_outer",
                expected_score=32,
                expected_command_events=6,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_nested_outer",
                expected_score=165,
                expected_command_events=12,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_discarded_frame",
                expected_score=1,
                expected_command_events=2,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_return_value_discard",
                expected_score=1,
                expected_command_events=None,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_return_run_outer",
                expected_score=31,
                expected_command_events=None,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_if_discard_outer",
                expected_score=31,
                expected_command_events=5,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_unless_discard_outer",
                expected_score=1032,
                expected_command_events=None,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:fused_execute_store_discard_outer",
                expected_score=32,
                expected_command_events=6,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:cbx_return_run_fail",
                expected_score=31,
                expected_command_events=5,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:cbx_nested_fail",
                expected_score=2031,
                expected_command_events=7,
            ),
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:cbx_unless_success",
                expected_score=2002,
                expected_command_events=6,
            ),
        ]
        time.sleep(1.1)
        debug_traces.append(
            run_debug_trace_fixture(
                client,
                mode,
                RUN_DIR,
                "function_compiler_probe:quota_nested_outer",
                expected_score=11,
                expected_command_events=3,
            )
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(client, mode, RUN_DIR, "quota_nested_outer")
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(client, mode, RUN_DIR, "quota_nested_inner")
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(client, mode, RUN_DIR, "quota_three")
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(client, mode, RUN_DIR, "quota_empty")
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(client, mode, RUN_DIR, "quota_one")
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(
                client, mode, RUN_DIR, "quota_execute_four"
            )
        )
        debug_traces.extend(
            [
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_return_result",
                    expected_score=17,
                    expected_command_events=4,
                ),
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_execute_if_function",
                    expected_score=11,
                    expected_command_events=4,
                ),
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_return_run",
                    expected_score=11,
                    expected_command_events=2,
                ),
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_return_run_exception",
                    expected_score=3,
                    expected_command_events=None,
                ),
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_execute_if_exception",
                    expected_score=3,
                    expected_command_events=None,
                ),
                run_debug_trace_fixture(
                    client,
                    mode,
                    RUN_DIR,
                    "function_compiler_probe:quota_execute_unless_exception",
                    expected_score=14,
                    expected_command_events=5,
                ),
            ]
        )
        debug_traces.extend(
            run_quota_debug_trace_sweep(
                client,
                mode,
                RUN_DIR,
                "quota_execute_unless_exception",
                quota_limits=range(17),
            )
        )
        persist_debug_traces(mode, debug_traces)
        queue_cost_trace = collect_queue_cost_trace(mode)

        client.command("stop")
        process.wait(timeout=45)
        return {
            "mode": mode,
            "server_jvm_args": list(RUNTIME_SERVER_JVM_ARGS),
            "gradle_daemon_jvm_args": RUNTIME_GRADLE_JVM_ARGS,
            "status": status,
            "post_execution_status": post_execution_status,
            "lifecycle_initial": lifecycle_initial,
            "lifecycle_functions": lifecycle_functions,
            "lifecycle_reloads": lifecycle_reloads,
            "queue_cost_trace": queue_cost_trace,
            "debug_traces": debug_traces,
            "scores_by_quota": scores,
            "commands": command_responses,
            "direct_function_fixtures": direct_fixtures,
            "fork_limit_fixture": fork_limit_fixture,
            "fork_order_fixture": fork_order_fixture,
            "scoreboard_semantics": scoreboard_semantics,
            "delegation_contract": delegation_contract,
            "score_add_prototype_metrics": score_add_metrics,
            "data_store_prototype_metrics": data_store_metrics,
            "bossbar_prototype_metrics": bossbar_metrics,
            "item_command_prototype_metrics": item_command_metrics,
            "fused_region_metrics": fused_region_metrics,
            "bytecode_region_metrics": bytecode_region_metrics,
            "score_add_timing_metrics": score_add_timing,
            "control_flow_fallback_cases": control_flow_fallback_cases,
            "command_callback_metric_fixture": callback_metric_fixture,
            "log": str(log_path.relative_to(ROOT)),
        }
    finally:
        if client is not None:
            client.close()
        if bot is not None:
            bot.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_handle.close()


def run_vanilla_reference(
    server_jar: Path,
    packet_ids: PacketIds,
    reload_cycles: int = 5,
    whole_reload_failure_probe: bool = False,
    concurrent_reload_probe: bool = False,
) -> dict[str, object]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    log_path = REPORT_DIR / "vanilla-reference.server.log"
    with tempfile.TemporaryDirectory(prefix="function-compiler-vanilla-") as temporary_dir:
        server_dir = Path(temporary_dir)
        lifecycle_pack_root = prepare_vanilla_files(server_dir)
        process, log_handle = start_vanilla_server(server_jar, server_dir, log_path)
        client: RconClient | None = None
        bot: PlayerBot | None = None
        try:
            client = wait_for_rcon(process)
            lifecycle_initial = initialize_lifecycle_pack(
                client,
                "mod-free-vanilla",
                ("function_compiler_probe",),
            )
            bot = connect_probe_player(packet_ids, client, "mod-free-vanilla")

            objective_response = client.command(f"scoreboard objectives add {OBJECTIVE} dummy")
            if "Unknown" in objective_response or "Incorrect" in objective_response:
                raise RuntimeError(f"Could not create probe objective: {objective_response!r}")
            prepare_modifier_actors(client, "mod-free-vanilla")

            direct_fixtures = run_direct_function_fixtures(client, "mod-free-vanilla")
            fork_limit_fixture = run_fork_limit_fixture(client, "mod-free-vanilla")
            fork_order_fixture = run_fork_order_fixture(client, "mod-free-vanilla")
            scoreboard_semantics = run_scoreboard_semantics(client, "mod-free-vanilla")
            delegation_contract = run_delegation_contract(client, "mod-free-vanilla")
            control_flow_fallback_cases = run_control_flow_fallback_cases(
                client, "mod-free-vanilla", server_dir
            )
            callback_metric_fixture = run_command_callback_metrics_fixture(
                client, "mod-free-vanilla", measure_callbacks=False
            )
            lifecycle_functions = run_lifecycle_functions(
                client, "mod-free-vanilla", server_dir
            )
            lifecycle_reloads = reload_lifecycle_pack(
                client,
                "mod-free-vanilla",
                lifecycle_pack_root,
                reload_cycles=reload_cycles,
                whole_reload_failure_probe=whole_reload_failure_probe,
                concurrent_reload_probe=concurrent_reload_probe,
            )
            debug_traces = [
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:quota_three",
                    expected_score=3,
                    expected_command_events=3,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:score_add_literal",
                    expected_score=7,
                    expected_command_events=1,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_missing_objective",
                    expected_score=22,
                    expected_command_events=6,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_result_fail_outer",
                    expected_score=32,
                    expected_command_events=6,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_success_return_value_outer",
                    expected_score=32,
                    expected_command_events=6,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_result_nested_return_outer",
                    expected_score=37,
                    expected_command_events=8,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_success_nested_return_outer",
                    expected_score=37,
                    expected_command_events=8,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_success_nested_fail_outer",
                    expected_score=37,
                    expected_command_events=8,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_result_discard_outer",
                    expected_score=32,
                    expected_command_events=6,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_nested_outer",
                    expected_score=165,
                    expected_command_events=12,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_discarded_frame",
                    expected_score=1,
                    expected_command_events=2,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_return_value_discard",
                    expected_score=1,
                    expected_command_events=None,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_return_run_outer",
                    expected_score=31,
                    expected_command_events=None,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_if_discard_outer",
                    expected_score=31,
                    expected_command_events=5,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_unless_discard_outer",
                    expected_score=1032,
                    expected_command_events=None,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:fused_execute_store_discard_outer",
                    expected_score=32,
                    expected_command_events=6,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:cbx_return_run_fail",
                    expected_score=31,
                    expected_command_events=5,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:cbx_nested_fail",
                    expected_score=2031,
                    expected_command_events=7,
                ),
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:cbx_unless_success",
                    expected_score=2002,
                    expected_command_events=6,
                ),
            ]
            time.sleep(1.1)
            debug_traces.append(
                run_debug_trace_fixture(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "function_compiler_probe:quota_nested_outer",
                    expected_score=11,
                    expected_command_events=3,
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client, "mod-free-vanilla", server_dir, "quota_nested_outer"
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client, "mod-free-vanilla", server_dir, "quota_nested_inner"
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client, "mod-free-vanilla", server_dir, "quota_three"
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client, "mod-free-vanilla", server_dir, "quota_empty"
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client, "mod-free-vanilla", server_dir, "quota_one"
                )
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "quota_execute_four",
                )
            )
            debug_traces.extend(
                [
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_return_result",
                        expected_score=17,
                        expected_command_events=4,
                    ),
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_execute_if_function",
                        expected_score=11,
                        expected_command_events=4,
                    ),
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_return_run",
                        expected_score=11,
                        expected_command_events=2,
                    ),
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_return_run_exception",
                        expected_score=3,
                        expected_command_events=None,
                    ),
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_execute_if_exception",
                        expected_score=3,
                        expected_command_events=None,
                    ),
                    run_debug_trace_fixture(
                        client,
                        "mod-free-vanilla",
                        server_dir,
                        "function_compiler_probe:quota_execute_unless_exception",
                        expected_score=14,
                        expected_command_events=5,
                    ),
                ]
            )
            debug_traces.extend(
                run_quota_debug_trace_sweep(
                    client,
                    "mod-free-vanilla",
                    server_dir,
                    "quota_execute_unless_exception",
                    quota_limits=range(17),
                )
            )
            persist_debug_traces("mod-free-vanilla", debug_traces)

            client.command("stop")
            process.wait(timeout=45)
            return {
                "mode": "mod-free-vanilla",
                "server_jvm_args": list(RUNTIME_SERVER_JVM_ARGS),
                "server_jar": "official Minecraft 26.3",
                "server_jar_sha256": SERVER_JAR_SHA256,
                "direct_function_fixtures": direct_fixtures,
                "fork_limit_fixture": fork_limit_fixture,
                "fork_order_fixture": fork_order_fixture,
                "scoreboard_semantics": scoreboard_semantics,
                "delegation_contract": delegation_contract,
                "control_flow_fallback_cases": control_flow_fallback_cases,
                "command_callback_metric_fixture": callback_metric_fixture,
                "lifecycle_initial": lifecycle_initial,
                "lifecycle_functions": lifecycle_functions,
                "lifecycle_reloads": lifecycle_reloads,
                "debug_traces": debug_traces,
                "log": str(log_path.relative_to(ROOT)),
            }
        finally:
            if client is not None:
                client.close()
            if bot is not None:
                bot.close()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
            log_handle.close()


def run_macro_probe_mode(
    mode: str,
    server_jar: Path,
    stack: str,
) -> dict[str, object]:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    log_path = REPORT_DIR / f"macro-{mode}-{stamp}.server.log"
    if mode == "mod-free-vanilla":
        with tempfile.TemporaryDirectory(prefix="function-compiler-macro-vanilla-") as temp:
            server_dir = Path(temp)
            prepare_vanilla_files(server_dir)
            process, log_handle = start_vanilla_server(server_jar, server_dir, log_path)
            client: RconClient | None = None
            try:
                client = wait_for_rcon(process)
                initialize_lifecycle_pack(client, mode)
                outcome = run_lifecycle_functions(client, mode, server_dir)
                client.command("stop")
                process.wait(timeout=45)
                return {"mode": mode, "outcome": outcome, "log": str(log_path.relative_to(ROOT))}
            finally:
                if client is not None:
                    client.close()
                if process.poll() is None:
                    process.terminate()
                    try:
                        process.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait(timeout=10)
                log_handle.close()

    prepare_macro_server_files(stack)
    process, log_handle = start_server(mode, log_path)
    client = None
    try:
        client = wait_for_rcon(process)
        initialize_lifecycle_pack(client, mode)
        outcome = run_lifecycle_functions(client, mode, RUN_DIR)
        client.command("stop")
        process.wait(timeout=45)
        return {
            "mode": mode,
            "stack": stack,
            "outcome": outcome,
            "log": str(log_path.relative_to(ROOT)),
        }
    finally:
        if client is not None:
            client.close()
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
        log_handle.close()


def run_macro_probe(
    selected_modes: tuple[str, ...] | None = None,
    stack: str = "fabric",
) -> int:
    server_jar = locate_official_server_jar()
    modes = selected_modes or (
        "mod-free-vanilla",
        "wrapper-off",
        "wrapper-on",
        "score-add-on",
        "instrument-only",
        "score-add-timed",
        "fused-interpreted",
        "bytecode-emitted",
        "selective-macro-arguments",
    )
    results = [run_macro_probe_mode(mode, server_jar, stack) for mode in modes]
    vanilla_result = next(
        (result for result in results if result["mode"] == "mod-free-vanilla"),
        None,
    )
    parity_checked = vanilla_result is not None

    def comparable_outcome(result: dict[str, object]) -> dict[str, object]:
        comparable = json.loads(json.dumps(result["outcome"]))
        comparable.pop("macro_specialization", None)
        comparable["entity_macro_arguments"].pop("debug_response", None)
        comparable["entity_macro_arguments"].pop("selected_call_counts", None)
        comparable["entity_macro_arguments"]["wrong_typed_data"].pop(
            "debug_response", None
        )
        comparable["entity_macro_arguments"]["wrong_typed_data"].pop(
            "selected_call_delta", None
        )
        comparable["entity_macro_arguments"]["composite_payload"].pop(
            "selected_call_delta", None
        )
        comparable["entity_macro_arguments"]["composite_payload"].pop(
            "storage_response", None
        )
        comparable["entity_macro_arguments"]["wrong_typed_storage_fallback"].pop(
            "debug_response", None
        )
        comparable["entity_macro_arguments"]["wrong_typed_storage_fallback"].pop(
            "selected_call_delta", None
        )
        comparable["entity_macro_arguments"]["wrong_typed_block_fallback"].pop(
            "debug_response", None
        )
        comparable["entity_macro_arguments"]["wrong_typed_block_fallback"].pop(
            "selected_call_delta", None
        )
        comparable["entity_macro_arguments"]["custom_entity_path_fallback"].pop(
            "debug_response", None
        )
        comparable["entity_macro_arguments"]["custom_entity_path_fallback"].pop(
            "selected_call_delta", None
        )
        comparable["entity_macro_arguments"]["nested_entity_path_fallback"].pop(
            "debug_response", None
        )
        comparable["entity_macro_arguments"]["nested_entity_path_fallback"].pop(
            "selected_call_delta", None
        )
        return comparable

    if vanilla_result is not None:
        baseline = comparable_outcome(vanilla_result)
        for result in results:
            if result is vanilla_result:
                continue
            comparable = comparable_outcome(result)
            if comparable != baseline:
                raise RuntimeError(
                    f"{result['mode']} macro behavior differs from vanilla: "
                    f"{comparable!r} != {baseline!r}"
                )
    compiler_off_result = next(
        (result for result in results if result["mode"] == "wrapper-off"),
        None,
    )
    selective_result = next(
        (result for result in results if result["mode"] == "selective-macro-arguments"),
        None,
    )
    same_stack_parity_checked = (
        compiler_off_result is not None and selective_result is not None
    )
    if same_stack_parity_checked and comparable_outcome(compiler_off_result) != comparable_outcome(selective_result):
        raise RuntimeError(
            f"selective macro behavior differs from same-stack compiler-off "
            f"on {stack}: {comparable_outcome(selective_result)!r} != "
            f"{comparable_outcome(compiler_off_result)!r}"
        )
    with server_jar.open("rb") as server_file:
        server_sha256 = hashlib.file_digest(server_file, "sha256").hexdigest()
    stack_mods = {
        MODS[key][0]: MODS[key][1]
        for key in STACK_MODS[stack]
    }
    report = {
        "benchmark": "MACRO-SPECIALIZATION-PROBE",
        "minecraft": "26.3",
        "server_jar_sha256": server_sha256,
        "stack": stack,
        "mods": stack_mods,
        "modes": results,
        "vanilla_macro_behavior_parity": parity_checked,
        "same_stack_compiler_off_parity": same_stack_parity_checked,
    }
    path = REPORT_DIR / f"macro-{time.strftime('%Y%m%dT%H%M%S', time.gmtime())}.results.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0


def _assert_fixture_high_quota_result(
    fixture: str,
    scores_by_quota: dict[int, int],
    mode: str,
) -> None:
    expected = EXPECTED_SCORES.get(fixture)
    if expected is None:
        return
    if scores_by_quota != expected:
        raise RuntimeError(
            f"{mode} {fixture} score sequence was {scores_by_quota}; expected {expected}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--macro-only",
        action="store_true",
        help="run the focused vanilla/macro-expansion specialization matrix",
    )
    parser.add_argument(
        "--macro-modes",
        nargs="+",
        choices=(
            "mod-free-vanilla", "wrapper-off", "wrapper-on", "score-add-on",
            "instrument-only", "score-add-timed", "fused-interpreted", "bytecode-emitted",
            "bytecode-compile-failure", "selective-macro-arguments",
        ),
        help="select arms for the focused macro probe (include mod-free-vanilla for parity)",
    )
    parser.add_argument(
        "--macro-stack",
        choices=tuple(STACK_MODS),
        default="fabric",
        help=(
            "pinned Fabric mod stack for non-vanilla macro arms; the vanilla arm "
            "always uses the official server"
        ),
    )
    parser.add_argument(
        "--modes",
        nargs="+",
        choices=(
            "wrapper-off", "wrapper-on", "mod-free-vanilla", "score-add-on",
            "instrument-only", "score-add-timed", "fused-interpreted",
            "bytecode-emitted", "bytecode-compile-failure",
            "selective-macro-arguments",
        ),
        help=(
            "select runtime-probe arms; include mod-free-vanilla as the semantic "
            "reference (defaults to the full matrix)"
        ),
    )
    parser.add_argument(
        "--reload-cycles",
        type=int,
        default=5,
        help="number of changed-body/tag reload generations (default: 5)",
    )
    parser.add_argument(
        "--whole-resource-reload-failure",
        action="store_true",
        help=(
            "load a test-only Fabric listener and compare retained lifecycle state "
            "after its forced server-data reload failure"
        ),
    )
    parser.add_argument(
        "--concurrent-resource-reload",
        action="store_true",
        help=(
            "hold the first Fabric resource preparation while six newer "
            "generations publish, then release the first and compare each "
            "publication with vanilla"
        ),
    )
    parser.add_argument(
        "--command-callback-metrics",
        action="store_true",
        help=(
            "opt in to callback wrappers and verify per-leaf generic versus "
            "ScoreAdd callback counts on an isolated function fixture"
        ),
    )
    arguments = parser.parse_args()
    if arguments.reload_cycles < 1:
        parser.error("--reload-cycles must be >= 1")
    configure_probe_ports()
    if arguments.macro_only or arguments.macro_modes:
        return run_macro_probe(
            tuple(arguments.macro_modes) if arguments.macro_modes else None,
            arguments.macro_stack,
        )
    if arguments.macro_stack != "fabric":
        parser.error("--macro-stack requires --macro-only or --macro-modes")

    vanilla_jar = locate_official_server_jar()
    packet_ids = generate_packet_ids(vanilla_jar)
    modes = arguments.modes or (
        "wrapper-off", "wrapper-on", "mod-free-vanilla", "score-add-on",
        "instrument-only", "score-add-timed", "fused-interpreted",
        "bytecode-emitted",
    )
    if "mod-free-vanilla" not in modes:
        parser.error("runtime parity runs must include mod-free-vanilla")
    if arguments.whole_resource_reload_failure and not any(
        mode != "mod-free-vanilla" for mode in modes
    ):
        parser.error(
            "--whole-resource-reload-failure requires at least one Fabric mode"
        )
    if arguments.concurrent_resource_reload and not any(
        mode != "mod-free-vanilla" for mode in modes
    ):
        parser.error("--concurrent-resource-reload requires at least one Fabric mode")
    if arguments.command_callback_metrics and not any(
        mode != "mod-free-vanilla" for mode in modes
    ):
        parser.error("--command-callback-metrics requires at least one Fabric mode")
    results = [
        run_vanilla_reference(
            vanilla_jar,
            packet_ids,
            reload_cycles=arguments.reload_cycles,
            whole_reload_failure_probe=arguments.whole_resource_reload_failure,
            concurrent_reload_probe=arguments.concurrent_resource_reload,
        )
        if mode == "mod-free-vanilla"
        else run_mode(
            mode,
            packet_ids,
            reload_cycles=arguments.reload_cycles,
            whole_reload_failure_probe=arguments.whole_resource_reload_failure,
            concurrent_reload_probe=arguments.concurrent_resource_reload,
            callback_metric_probe=arguments.command_callback_metrics,
        )
        for mode in modes
    ]
    results_by_mode = {str(result["mode"]): result for result in results}
    if arguments.concurrent_resource_reload:
        vanilla_publication = results_by_mode["mod-free-vanilla"][
            "lifecycle_reloads"
        ]["concurrent_reload_publication"]
        if not isinstance(vanilla_publication, dict):
            raise RuntimeError("Vanilla reference omitted concurrent reload evidence")
        if vanilla_publication.get("preparation_gate_entered") is not False:
            raise RuntimeError("Vanilla reference unexpectedly used the Fabric reload gate")
        for mode_result in (
            result for result in results if result["mode"] != "mod-free-vanilla"
        ):
            publication = mode_result["lifecycle_reloads"][
                "concurrent_reload_publication"
            ]
            if not isinstance(publication, dict):
                raise RuntimeError(
                    f"{mode_result['mode']} omitted concurrent reload evidence"
                )
            if publication.get("preparation_gate_entered") is not True:
                raise RuntimeError(
                    f"{mode_result['mode']} did not hold async preparation"
                )
            for field in (
                "old_generation_during_preparation",
                "overlap_generation_after_second",
                "overlap_generation_after_third",
                "overlap_generation_after_fourth",
                "overlap_generation_after_fifth",
                "overlap_generation_after_sixth",
                "new_generation_after_publication",
            ):
                if publication[field] != vanilla_publication[field]:
                    raise RuntimeError(
                        f"{mode_result['mode']} {field} differs from vanilla: "
                        f"{publication[field]!r} vs {vanilla_publication[field]!r}"
                    )
            if publication["overlap_load_count_after_second"] != (
                publication["load_count_before"] + 1
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} second reload did not publish while "
                    "the first reload was held"
                )
            if publication["overlap_load_count_after_third"] != (
                publication["load_count_before"] + 2
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} third reload did not publish while "
                    "the first reload was held"
                )
            if publication["overlap_load_count_after_fourth"] != (
                publication["load_count_before"] + 3
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} fourth reload did not publish while "
                    "the first reload was held"
                )
            if publication["overlap_load_count_after_fifth"] != (
                publication["load_count_before"] + 4
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} fifth reload did not publish while "
                    "the first reload was held"
                )
            if publication["overlap_load_count_after_sixth"] != (
                publication["load_count_before"] + 5
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} sixth reload did not publish while "
                    "the first reload was held"
                )
            if publication["overlap_load_count_after_seventh"] != (
                publication["load_count_before"] + 6
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} seventh reload did not publish while "
                    "the first reload was held"
                )
            if publication["load_count_after"] != publication["load_count_before"] + 7:
                raise RuntimeError(
                    f"{mode_result['mode']} overlapping reloads did not each "
                    "run the load tag exactly once"
                )
    wrapper_off = results_by_mode.get("wrapper-off")
    if wrapper_off is not None and "wrapper-on" in results_by_mode:
        off_scores = wrapper_off["scores_by_quota"]
        on_scores = results_by_mode["wrapper-on"]["scores_by_quota"]
        if off_scores != on_scores:
            raise RuntimeError(
                f"Wrapper changed quota results: off={off_scores}, on={on_scores}"
            )
    # Fused and bytecode regions intentionally combine multiple original queue
    # entries. Compare their semantic results and command-level debug traces,
    # while retaining physical queue-boundary checks for entry backends.
    entry_backend_modes = {
        "wrapper-on", "score-add-on", "instrument-only", "score-add-timed",
        "bytecode-compile-failure",
    }
    if wrapper_off is not None:
        entry_backend_results = (
            result for result in results if result["mode"] in entry_backend_modes
        )
        for mode_result in entry_backend_results:
            if wrapper_off["queue_cost_trace"] == mode_result["queue_cost_trace"]:
                continue
            off_trace = wrapper_off["queue_cost_trace"]
            on_trace = mode_result["queue_cost_trace"]
            first_difference = next(
                (
                    (
                        index,
                        off_trace[index] if index < len(off_trace) else None,
                        on_trace[index] if index < len(on_trace) else None,
                    )
                    for index in range(max(len(off_trace), len(on_trace)))
                    if (off_trace[index] if index < len(off_trace) else None)
                    != (on_trace[index] if index < len(on_trace) else None)
                ),
                None,
            )
            raise RuntimeError(
                f"{mode_result['mode']} changed the captured helper-path quota/cost trace: "
                f"first difference={first_difference}, lengths={len(off_trace)}/{len(on_trace)}; "
                f"saved {REPORT_DIR}/wrapper-off.queue-trace.json and "
                f"{REPORT_DIR}/{mode_result['mode']}.queue-trace.json"
            )

    vanilla_result = results_by_mode["mod-free-vanilla"]
    reference = vanilla_result["direct_function_fixtures"]
    vanilla_lifecycle = vanilla_result["lifecycle_functions"]
    vanilla_lifecycle_generations = vanilla_result["lifecycle_reloads"]["generations"]
    def _extract_debug_outcome(item: dict[str, object]) -> dict[str, object]:
        return {
            "function": item["function"],
            "quota": item.get("quota"),
            "score": item["score"],
            "command_events": item["command_events"],
            "trace": item["trace"],
        }

    vanilla_debug_outcomes = [
        _extract_debug_outcome(item) for item in vanilla_result["debug_traces"]
    ]
    for mode_result in (
        result for result in results if result["mode"] != "mod-free-vanilla"
    ):
        for fixture in DIRECT_FIXTURES:
            mode_scores = mode_result["direct_function_fixtures"][fixture]["scores_by_quota"]
            reference_scores = reference[fixture]["scores_by_quota"]
            if mode_scores != reference_scores:
                raise RuntimeError(
                    f"{mode_result['mode']} differs from mod-free vanilla for {fixture}: "
                    f"{mode_scores} vs {reference_scores}"
                )
            mode_responses = mode_result["direct_function_fixtures"][fixture]["commands"]
            reference_responses = reference[fixture]["commands"]
            if mode_responses != reference_responses:
                raise RuntimeError(
                    f"{mode_result['mode']} command results differ from mod-free vanilla "
                    f"for {fixture}"
                )

        mode_forks = mode_result["fork_limit_fixture"]["match_cases"]
        reference_forks = vanilla_result["fork_limit_fixture"]["match_cases"]
        if mode_forks != reference_forks:
            raise RuntimeError(
                f"{mode_result['mode']} differs from mod-free vanilla for fork limits: "
                f"{mode_forks} vs {reference_forks}"
            )
        mode_shapes = mode_result["fork_limit_fixture"]["selector_shape_cases"]
        reference_shapes = vanilla_result["fork_limit_fixture"][
            "selector_shape_cases"
        ]
        if mode_shapes != reference_shapes:
            raise RuntimeError(
                f"{mode_result['mode']} differs from mod-free vanilla for fork "
                f"selector shapes: {mode_shapes} vs {reference_shapes}"
            )

        if mode_result["fork_order_fixture"] != vanilla_result["fork_order_fixture"]:
            raise RuntimeError(
                f"{mode_result['mode']} differs from mod-free vanilla for ordered fork effects"
            )

        if mode_result["scoreboard_semantics"] != vanilla_result["scoreboard_semantics"]:
            raise RuntimeError(
                f"{mode_result['mode']} scoreboard command results differ from "
                "mod-free vanilla"
            )

        mode_control_flow = json.loads(
            json.dumps(mode_result["control_flow_fallback_cases"])
        )
        vanilla_control_flow = json.loads(
            json.dumps(vanilla_result["control_flow_fallback_cases"])
        )
        for case in (mode_control_flow, vanilla_control_flow):
            for case_name in (
                "execute_if_return_fail_discards_fused_tails",
                "execute_unless_return_fail_runs_branch_discards_fused_tails",
                "execute_store_success_return_fail_discards_fused_tails",
                "execute_store_success_return_value_discards_fused_tails",
                "execute_store_success_nested_return_discards_fused_tails",
                "execute_store_success_nested_fail_discards_fused_tails",
                "execute_store_result_nested_return_discards_fused_tails",
                "execute_store_result_return_value_discards_fused_tails",
                "execute_store_result_return_fail_discards_fused_tails",
                "return_run_child_fail_discards_fused_tails",
                "nested_child_fail_resumes_parent_tail",
                "execute_unless_child_success_skips_branch",
            ):
                candidate = case.get(case_name)
                if candidate is not None:
                    candidate.pop("backend_region_metrics", None)
        if mode_control_flow != vanilla_control_flow:
            mode_cases = mode_result["control_flow_fallback_cases"]
            vanilla_cases = vanilla_result["control_flow_fallback_cases"]
            mismatch = {
                name: {
                    "mode": repr(mode_cases.get(name))[:1200],
                    "vanilla": repr(vanilla_cases.get(name))[:1200],
                }
                for name in sorted(set(mode_cases) | set(vanilla_cases))
                if mode_cases.get(name) != vanilla_cases.get(name)
            }
            raise RuntimeError(
                f"{mode_result['mode']} fallback/exception behavior differs from "
                f"mod-free vanilla: {mismatch!r}"
            )

        callback_metric_state = {
            key: mode_result["command_callback_metric_fixture"][key]
            for key in ("score", "forked_actor_count")
        }
        vanilla_callback_metric_state = {
            key: vanilla_result["command_callback_metric_fixture"][key]
            for key in ("score", "forked_actor_count")
        }
        if callback_metric_state != vanilla_callback_metric_state:
            raise RuntimeError(
                f"{mode_result['mode']} callback metric fixture state differs "
                "from mod-free vanilla"
            )

        mode_macro_outcome = json.loads(
            json.dumps(mode_result["lifecycle_functions"])
        )
        vanilla_macro_outcome = json.loads(json.dumps(vanilla_lifecycle))
        mode_macro_outcome.pop("macro_specialization", None)
        vanilla_macro_outcome.pop("macro_specialization", None)
        for outcome in (mode_macro_outcome, vanilla_macro_outcome):
            outcome["entity_macro_arguments"].pop("debug_response", None)
            outcome["entity_macro_arguments"].pop("selected_call_counts", None)
            outcome["entity_macro_arguments"]["wrong_typed_data"].pop(
                "debug_response", None
            )
            outcome["entity_macro_arguments"]["wrong_typed_data"].pop(
                "selected_call_delta", None
            )
            outcome["entity_macro_arguments"]["composite_payload"].pop(
                "selected_call_delta", None
            )
            outcome["entity_macro_arguments"]["composite_payload"].pop(
                "storage_response", None
            )
            outcome["entity_macro_arguments"]["wrong_typed_storage_fallback"].pop(
                "debug_response", None
            )
            outcome["entity_macro_arguments"]["wrong_typed_storage_fallback"].pop(
                "selected_call_delta", None
            )
            outcome["entity_macro_arguments"]["wrong_typed_block_fallback"].pop(
                "debug_response", None
            )
            outcome["entity_macro_arguments"]["wrong_typed_block_fallback"].pop(
                "selected_call_delta", None
            )
            outcome["entity_macro_arguments"]["custom_entity_path_fallback"].pop(
                "debug_response", None
            )
            outcome["entity_macro_arguments"]["custom_entity_path_fallback"].pop(
                "selected_call_delta", None
            )
            outcome["entity_macro_arguments"]["nested_entity_path_fallback"].pop(
                "debug_response", None
            )
            outcome["entity_macro_arguments"]["nested_entity_path_fallback"].pop(
                "selected_call_delta", None
            )
        if mode_macro_outcome != vanilla_macro_outcome:
            differing = sorted(
                key
                for key in set(mode_macro_outcome) | set(vanilla_macro_outcome)
                if mode_macro_outcome.get(key) != vanilla_macro_outcome.get(key)
            )
            raise RuntimeError(
                f"{mode_result['mode']} lifecycle function or macro behavior differs "
                f"from mod-free vanilla at {differing}: "
                + "; ".join(
                    f"{key}={repr(mode_macro_outcome.get(key))[:220]} vs "
                    f"{repr(vanilla_macro_outcome.get(key))[:220]}"
                    for key in differing
                )
            )
        mode_generations = mode_result["lifecycle_reloads"]["generations"]
        comparable_keys = (
            "generation",
            "load_count",
            "direct_score",
            "tag_score",
            "tag_targets_probe_v2",
        )
        mode_generation_outcomes = [
            {key: item[key] for key in comparable_keys} for item in mode_generations
        ]
        vanilla_generation_outcomes = [
            {key: item[key] for key in comparable_keys}
            for item in vanilla_lifecycle_generations
        ]
        if mode_generation_outcomes != vanilla_generation_outcomes:
            raise RuntimeError(
                f"{mode_result['mode']} reload outcomes differ from mod-free vanilla"
            )
        removal_addition_keys = (
            "removed_load_count",
            "removed_function_response",
            "removed_function_score",
            "tag_after_removal_score",
            "readded_load_count",
            "readded_direct_response",
            "readded_direct_score",
            "readded_tag_response",
            "readded_tag_score",
        )
        mode_removal_addition = {
            key: mode_result["lifecycle_reloads"]["removal_addition"][key]
            for key in removal_addition_keys
        }
        vanilla_removal_addition = {
            key: vanilla_result["lifecycle_reloads"]["removal_addition"][key]
            for key in removal_addition_keys
        }
        if mode_removal_addition != vanilla_removal_addition:
            raise RuntimeError(
                f"{mode_result['mode']} remove/re-add outcomes differ from mod-free vanilla"
            )
        malformed_keys = (
            "load_count_before",
            "load_count_after",
            "load_count_delta",
            "parse_error_logged",
            "invalid_function_response",
            "invalid_function_score",
            "valid_direct_score",
            "valid_tag_score",
        )
        mode_malformed_reload = {
            key: mode_result["lifecycle_reloads"]["malformed_function_parse"][key]
            for key in malformed_keys
        }
        vanilla_malformed_reload = {
            key: vanilla_result["lifecycle_reloads"]["malformed_function_parse"][key]
            for key in malformed_keys
        }
        if mode_malformed_reload != vanilla_malformed_reload:
            raise RuntimeError(
                f"{mode_result['mode']} malformed-function reload differs "
                "from mod-free vanilla"
            )
        malformed_macro_keys = (
            "load_count_before",
            "load_count_after",
            "load_count_delta",
            "parse_error_logged",
            "invalid_function_response",
            "valid_macro_score",
            "valid_macro_body_marker",
        )
        mode_malformed_macro_reload = {
            key: mode_result["lifecycle_reloads"][
                "malformed_macro_template_parse"
            ][key]
            for key in malformed_macro_keys
        }
        vanilla_malformed_macro_reload = {
            key: vanilla_result["lifecycle_reloads"][
                "malformed_macro_template_parse"
            ][key]
            for key in malformed_macro_keys
        }
        if mode_malformed_macro_reload != vanilla_malformed_macro_reload:
            raise RuntimeError(
                f"{mode_result['mode']} malformed-macro reload differs "
                "from mod-free vanilla"
            )
        if arguments.whole_resource_reload_failure:
            vanilla_whole_reload = vanilla_result["lifecycle_reloads"][
                "whole_resource_reload_failure"
            ]
            mode_whole_reload = mode_result["lifecycle_reloads"][
                "whole_resource_reload_failure"
            ]
            if not isinstance(vanilla_whole_reload, dict) or not isinstance(
                mode_whole_reload, dict
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} omitted whole-resource reload evidence"
                )
            if mode_whole_reload.get("injected") is not True:
                raise RuntimeError(
                    f"{mode_result['mode']} did not inject the resource reload failure"
                )
            if not mode_whole_reload.get("listener_observed") or not mode_whole_reload.get(
                "exception_logged"
            ):
                raise RuntimeError(
                    f"{mode_result['mode']} did not verify the injected reload exception"
                )
            if mode_whole_reload.get("baseline") != vanilla_whole_reload.get("baseline"):
                raise RuntimeError(
                    f"{mode_result['mode']} pre-failure lifecycle state differs from vanilla"
                )
            if mode_whole_reload.get("after") != vanilla_whole_reload.get("baseline"):
                raise RuntimeError(
                    f"{mode_result['mode']} failed reload changed state from the vanilla baseline"
                )
        debug_outcomes = [
            _extract_debug_outcome(item) for item in mode_result["debug_traces"]
        ]
        if debug_outcomes != vanilla_debug_outcomes:
            mismatch = next(
                (
                    (index, actual, expected)
                    for index, (actual, expected) in enumerate(
                        zip(debug_outcomes, vanilla_debug_outcomes)
                    )
                    if actual != expected
                ),
                None,
            )
            raise RuntimeError(
                f"{mode_result['mode']} debug traces differ from mod-free vanilla; "
                f"first mismatch={mismatch!r}, trace counts="
                f"{len(debug_outcomes)}/{len(vanilla_debug_outcomes)}. "
                f"Per-mode traces are saved under {REPORT_DIR}/*.debug-trace-*.txt"
            )
        if not mode_result["lifecycle_initial"]["tick_progressed"]:
            raise RuntimeError(f"{mode_result['mode']} did not run the tick tag")

    if arguments.concurrent_resource_reload:
        output_name = "concurrent-resource-reload-results.json"
    elif arguments.whole_resource_reload_failure:
        output_name = "whole-resource-reload-failure-results.json"
    elif arguments.command_callback_metrics:
        output_name = "command-callback-metrics-results.json"
    else:
        output_name = "results.json"
    output_path = REPORT_DIR / output_name
    output_path.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    for mode_result in results:
        direct = mode_result["direct_function_fixtures"]
        summaries = {
            name: direct[name]["scores_by_quota"]
            for name in (
                "quota_return_value",
                "quota_return_run",
                "quota_return_result",
                "quota_execute_if_function",
                "quota_nested_return_outer",
                "quota_recursive",
                "quota_recursive_compiled",
                "quota_change_limit",
            )
        }
        forks = [
            (item["match_count"], item["scores_by_fork_limit"])
            for item in mode_result["fork_limit_fixture"]["match_cases"]
        ]
        reloads = [
            (
                item["load_count"],
                item["direct_score"],
                item["tag_score"],
                item["tag_targets_probe_v2"],
            )
            for item in mode_result["lifecycle_reloads"]["generations"]
        ]
        removal_addition = mode_result["lifecycle_reloads"]["removal_addition"]
        malformed_function_parse = mode_result["lifecycle_reloads"][
            "malformed_function_parse"
        ]
        print(
            f"{mode_result['mode']}: extended={summaries}; forks={forks}; "
            f"reloads={reloads}; removal_addition={removal_addition}; "
            f"malformed_function_parse={malformed_function_parse}; "
            f"debug_traces={len(mode_result['debug_traces'])}"
        )
    compared_modes = [
        str(result["mode"]) for result in results if result["mode"] != "mod-free-vanilla"
    ]
    print(
        f"Mod-free vanilla matches {', '.join(compared_modes)} for direct-function "
        f"state, results, traces, reloads, and forks across {', '.join(DIRECT_FIXTURES)}. "
        f"Report: {output_path}"
    )
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"Runtime probe failed: {error}", file=sys.stderr)
        raise
