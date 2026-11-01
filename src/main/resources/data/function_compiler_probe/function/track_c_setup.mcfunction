scoreboard objectives add fc_probe dummy
scoreboard players set #tag_active_found fc_probe 0
scoreboard players set #tag_active_removed fc_probe 0
scoreboard players set #tag_active_gone fc_probe 0
scoreboard players set #track_c_done fc_probe 0

summon armor_stand 10 70 10 {Tags:["fc_c_source"]}
summon armor_stand 20 70 20 {Tags:["fc_c_target"]}
