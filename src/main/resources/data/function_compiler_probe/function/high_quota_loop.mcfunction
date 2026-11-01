scoreboard players add #quota_loop fc_probe 1
execute if score #quota_loop fc_probe matches 1..2000 run function function_compiler_probe:high_quota_loop
