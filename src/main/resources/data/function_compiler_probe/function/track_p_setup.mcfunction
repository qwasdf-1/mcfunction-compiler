scoreboard objectives add fc_probe dummy
scoreboard players set #item_done fc_probe 0
kill @e[tag=fc_p_target]
summon armor_stand 0 64 0 {Tags:["fc_p_target"]}
