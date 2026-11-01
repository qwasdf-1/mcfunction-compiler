execute if function function_compiler_probe:quota_condition_success run scoreboard players add #fcprobe fc_probe 1
execute unless function function_compiler_probe:quota_condition_failure run scoreboard players add #fcprobe fc_probe 10
