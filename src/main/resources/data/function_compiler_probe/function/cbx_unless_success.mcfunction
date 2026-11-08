# execute unless function around a child that returns a value: the child's
# pending fused tail is discarded and the unless branch must be skipped,
# with the parent's own pending fused tail resuming once.
scoreboard players add #fcprobe fc_probe 1
execute unless function function_compiler_probe:quota_nested_return_inner run scoreboard players add #fcprobe fc_probe 10
scoreboard players add #fcprobe fc_probe 1000
scoreboard players add #fcprobe fc_probe 1000
