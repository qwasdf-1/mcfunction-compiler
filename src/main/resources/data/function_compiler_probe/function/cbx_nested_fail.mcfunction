# Plain nested call around a child that returns fail: the child's pending
# fused tail is discarded, the parent's pending fused tail still runs.
scoreboard players add #fcprobe fc_probe 1
function function_compiler_probe:cbx_return_run_fail_child
scoreboard players add #fcprobe fc_probe 1000
scoreboard players add #fcprobe fc_probe 1000
