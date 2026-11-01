scoreboard players set #callback_metrics fc_probe 1
scoreboard players add #callback_metrics fc_probe 2
scoreboard players add #callback_metrics fc_probe 3
execute as @e[type=minecraft:armor_stand,tag=fc_callback_metrics_actor] run scoreboard players set @s fc_probe 9
say callback-metrics-probe
