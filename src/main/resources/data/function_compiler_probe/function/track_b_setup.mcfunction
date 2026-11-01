scoreboard objectives add fc_probe dummy
scoreboard players set #pred_if_ent fc_probe 0
scoreboard players set #pred_unless_ent fc_probe 0
scoreboard players set #pred_if_missing fc_probe 0
scoreboard players set #pred_unless_present fc_probe 0
scoreboard players set #pred_if_pred fc_probe 0
scoreboard players set #pred_unless_pred fc_probe 0
scoreboard players set #pred_fail_pred fc_probe 0
scoreboard players set #pred_fail_unless_pred fc_probe 0
scoreboard players set #pred_self fc_probe 0

summon armor_stand 0 100 0 {Tags:["fc_track_b_tag_a"]}
summon armor_stand 0 100 0 {Tags:["fc_track_b_tag_b"]}
