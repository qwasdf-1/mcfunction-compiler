scoreboard players add #tramp_depth fc_probe 1
scoreboard players add #tramp_pre fc_probe 1
execute if score #tramp_depth fc_probe matches 50.. run return 77
function function_compiler_probe:exotic_trampoline_b
scoreboard players add #tramp_post fc_probe 1
