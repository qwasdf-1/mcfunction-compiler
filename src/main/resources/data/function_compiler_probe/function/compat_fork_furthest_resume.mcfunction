execute positioned 32 100 0 as @e[type=minecraft:armor_stand,tag=fc_compat_order,sort=furthest,limit=2] run scoreboard players operation #fc_compat_fork_acc fc_compat_order >< @s fc_compat_order
scoreboard players add #fc_compat_fork_followup fc_compat_order 10
