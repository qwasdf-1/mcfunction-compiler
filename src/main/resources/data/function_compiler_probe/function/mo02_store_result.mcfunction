# Coverage row MO-02, first half: the `DataStore` modifier around data
# commands, `execute store result|success storage <id> <path> <type> <scale>
# run ...`, on the paths where the inner data command succeeds.
#
# 26.3 syntax fact, read from the pinned vanilla server rather than assumed:
# the tree is `execute store (result|success) storage <target> <path> <type>
# <scale> run <command>`. The type is a literal among byte/short/int/long/
# float/double and the scale is a required double; omitting the scale is
# rejected at `run` with "Expected double...", and omitting the type is
# rejected at the type position. That is the eight-node shape
# DataStoreParser.java checks (execute, store, result|success, storage,
# target, path, <type>, scale).
#
# The oracle is the storage content itself, matched exactly with
# `execute if data storage <id> {probe: <value>}` and folded into #fcprobe as
# power-of-two weights. Exact matching also pins the NBT tag type: a store that
# ignored the `byte` literal would write an int and the -112b match would fail.
# Every case is a taken branch, so a truncated tail lowers the total instead of
# looking like an executed case. The last case takes a branch, which makes it
# the completion signal.
#
# Case 1 (+2) stores the result of a successful read with `byte` type and
# scale 2. The source is 200, so the stored value is (byte)(200 * 2) = -112.
# That one value proves the result path, the scale multiplication and the type
# conversion at once: ignoring the scale would store (byte)200 = -56, and
# ignoring the type would store 400.
#
# Case 2 (+1) is `store success` on a successful read with `short` type. The
# success value 1 is stored as 1s, which proves the success path and its type
# literal. It is the final case and always fires on a complete run.
#
# expected 1,1 = 3
data modify storage function_compiler_probe:mo02store big set value 200
execute store result storage function_compiler_probe:mo02store probe byte 2 run data get storage function_compiler_probe:mo02store big
execute if data storage function_compiler_probe:mo02store {probe: -112b} run scoreboard players add #fcprobe fc_probe 2
execute store success storage function_compiler_probe:mo02store probe short 1 run data get storage function_compiler_probe:mo02store big
execute if data storage function_compiler_probe:mo02store {probe: 1s} run scoreboard players add #fcprobe fc_probe 1
