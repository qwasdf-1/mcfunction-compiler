scoreboard players reset @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 2
scoreboard players add @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 3
scoreboard players set #actor_sum fc_probe 0
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] run scoreboard players operation #actor_sum fc_probe += @s fc_probe
