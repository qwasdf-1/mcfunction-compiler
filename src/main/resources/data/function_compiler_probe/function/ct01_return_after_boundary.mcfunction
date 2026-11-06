# Coverage row CT-01: a return callback after a fused-region boundary discards
# the pending tail.
#
# The fixture has two frames, and each one has the same shape: a fused region,
# then a non-fusable `say` boundary, then a second fused region, then a return.
# The completed regions on both sides of each boundary must persist; the commands
# after the return are the pending tail and must not run.
#
# The outer frame adds 1, crosses its boundary, adds 10 and 20, then uses
# `return run function` to call the child. That return discards the outer tail
# (+100). The child adds 100, crosses its own boundary, adds 200, and returns 7;
# its return discards the child tail (+1000). The result 7 propagates through
# `return run` to the top-level function result, which the runner compares in
# the command response as well as the score.
#
# A compiler that resumed the outer tail after the child, or replayed either
# completed region when unwinding, changes the total; one that dropped the
# `return run` result changes the response.
scoreboard players add #fcprobe fc_probe 1
say ct01-outer-boundary
scoreboard players add #fcprobe fc_probe 10
scoreboard players add #fcprobe fc_probe 20
return run function function_compiler_probe:ct01_child_return
scoreboard players add #fcprobe fc_probe 100
