tag @e[tag=fc_c_target] add fc_tag_active
execute as @e[tag=fc_c_target] run tag @s add fc_tag_nested
execute as @e[tag=fc_c_target] if entity @s[tag=fc_tag_active] run scoreboard players add #tag_active_found fc_probe 1
tp @e[tag=fc_c_target] 100 80 100
execute as @e[tag=fc_c_target] at @s run tag @s remove fc_tag_active
execute as @e[tag=fc_c_target] if entity @s[tag=fc_tag_active] run scoreboard players add #tag_active_removed fc_probe 999
execute as @e[tag=fc_c_target] unless entity @s[tag=fc_tag_active] run scoreboard players add #tag_active_gone fc_probe 1
execute as @e[tag=fc_c_target] run tp @s ~ ~5 ~
execute as @e[tag=fc_c_target] run scoreboard players add #track_c_done fc_probe 1
