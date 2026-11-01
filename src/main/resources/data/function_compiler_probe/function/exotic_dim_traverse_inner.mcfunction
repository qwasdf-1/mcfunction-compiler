scoreboard players add #dim_runner_steps fc_probe 1
execute in minecraft:the_nether run tp @s 0 64 0
scoreboard players add #dim_runner_steps fc_probe 1
execute at @s run setblock 0 64 0 minecraft:netherrack
execute in minecraft:the_end run tp @s 100 50 0
scoreboard players add #dim_runner_steps fc_probe 1
execute in minecraft:overworld run tp @s 0 64 0
scoreboard players add #dim_runner_steps fc_probe 1
