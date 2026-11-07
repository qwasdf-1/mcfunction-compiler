# Coverage row MO-02, second half: the `DataStore` modifier around data
# commands on the paths where the inner data command throws. The successful
# result/success paths live in mo02_store_result; this fixture is separate
# because a failing `data get` costs about eight points of the command-sequence
# budget, so one fixture cannot hold both halves inside the 0-16 sweep.
#
# 26.3 failure fact, read from the pinned vanilla server rather than assumed:
# a `data get` on an absent path throws, and vanilla's execute framework then
# reports (success=false, result=0) to the store callback. The store callback
# writes that value for a *result* store as well as a success store, so both
# kinds overwrite the previous content with a zero of the declared type. The
# earlier DS-05 note that a failing result store leaves the store unapplied was
# wrong for this reason; the measured write is 0.
#
# The oracle is the storage content itself, matched exactly with
# `execute if data storage <id> {probe: <value>}` and folded into #fcprobe as
# power-of-two weights. The distinct tag suffixes (0L and 0s) also pin the type
# literal. Every case is a taken branch, so a truncated tail lowers the total
# instead of looking like an executed error case. The last case takes a branch,
# which makes it the completion signal.
#
# Case 1 (+2) seeds the path with 9 and then runs `store result` on a failed
# read with `long` type. The path must hold 0L: a specialization that skipped
# the write would leave 9, and one that ignored the type would write an int.
#
# Case 2 (+1) seeds the path with 9 and runs `store success` on a failed read
# with `short` type. The path must hold 0s, so the failed read still stores the
# success value 0. It is the final case and always fires on a complete run.
#
# expected 1,1 = 3
data modify storage function_compiler_probe:mo02store probe set value 9
execute store result storage function_compiler_probe:mo02store probe long 2 run data get storage function_compiler_probe:mo02store absent.path
execute if data storage function_compiler_probe:mo02store {probe: 0L} run scoreboard players add #fcprobe fc_probe 2
data modify storage function_compiler_probe:mo02store probe set value 9
execute store success storage function_compiler_probe:mo02store probe short 3 run data get storage function_compiler_probe:mo02store absent.path
execute if data storage function_compiler_probe:mo02store {probe: 0s} run scoreboard players add #fcprobe fc_probe 1
