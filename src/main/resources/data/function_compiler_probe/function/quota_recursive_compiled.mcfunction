scoreboard players add #fcprobe fc_probe 1
scoreboard players add #fcprobe fc_probe 1
execute if score #fcprobe fc_probe matches 1..5 run function function_compiler_probe:quota_recursive_compiled
