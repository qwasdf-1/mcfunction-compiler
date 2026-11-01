scoreboard players add #k_counter fc_probe 1
execute if score #k_counter fc_probe matches 1..9 run function function_compiler_probe:track_k_loop
