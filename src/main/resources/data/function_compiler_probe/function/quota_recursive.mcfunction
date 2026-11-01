scoreboard players add #fcprobe fc_probe 1
execute if score #fcprobe fc_probe matches 1..3 run function function_compiler_probe:quota_recursive
