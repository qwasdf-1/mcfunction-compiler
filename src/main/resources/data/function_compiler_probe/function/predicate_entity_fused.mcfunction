execute if entity @s run scoreboard players add #pred_e fc_probe 10
execute unless entity @s run scoreboard players add #pred_e fc_probe 100
execute as @e[tag=fc_self_actor,limit=1] if entity @s run scoreboard players add #pred_e fc_probe 25
execute as @e[tag=fc_self_actor,limit=1] unless entity @s run scoreboard players add #pred_e fc_probe 200
