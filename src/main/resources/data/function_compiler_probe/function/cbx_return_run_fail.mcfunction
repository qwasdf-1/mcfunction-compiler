# return run around a child that returns fail: the child's pending fused
# tail must be discarded while the parent's own pending tail still runs.
scoreboard players add #fcprobe fc_probe 1
return run function function_compiler_probe:cbx_return_run_fail_child
scoreboard players add #fcprobe fc_probe 1000
scoreboard players add #fcprobe fc_probe 1000
