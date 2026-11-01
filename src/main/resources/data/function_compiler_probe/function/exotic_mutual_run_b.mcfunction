scoreboard players add #mut_depth fc_probe 1
scoreboard players add #mut_count_b fc_probe 1
scoreboard players operation #mut_accum fc_probe += #mut_depth fc_probe
execute if score #mut_depth fc_probe matches 100.. run return 100
return run function function_compiler_probe:exotic_mutual_run_a
