scoreboard players add #macro_rec_depth fc_probe 1
scoreboard players add #macro_rec_a fc_probe 1
$scoreboard players set #macro_param_a fc_probe $(n)
scoreboard players operation #macro_accum fc_probe += #macro_param_a fc_probe
execute if score #macro_rec_depth fc_probe matches 50.. run return run scoreboard players get #macro_accum fc_probe
$scoreboard players set #next_n fc_probe $(n)
scoreboard players add #next_n fc_probe 1
execute store result storage redteam:rec_n n int 1 run scoreboard players get #next_n fc_probe
return run function function_compiler_probe:exotic_macro_rec_b with storage redteam:rec_n
