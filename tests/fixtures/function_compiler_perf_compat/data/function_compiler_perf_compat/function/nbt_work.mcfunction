execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] store result score @s fc_perf run data get entity @s Health 1000
execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] run data modify entity @s NoAI set value 1b
execute as @e[type=minecraft:zombie,tag=fc_perf_nbt] run scoreboard players add #nbt_targets fc_perf 1
