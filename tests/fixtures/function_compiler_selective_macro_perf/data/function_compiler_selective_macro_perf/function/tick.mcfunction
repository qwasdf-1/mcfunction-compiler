scoreboard players add #server_ticks fc_macro 1
execute if score #enabled fc_macro matches 1 as @e[type=minecraft:marker,tag=fc_macro_source] at @s run function function_compiler_selective_macro_perf:repeat
execute if score #enabled fc_macro matches 1 run scoreboard players add #active_ticks fc_macro 1
