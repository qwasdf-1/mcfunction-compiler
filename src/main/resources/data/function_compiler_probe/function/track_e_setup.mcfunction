scoreboard objectives add fc_probe dummy
scoreboard objectives add leaf_score dummy
scoreboard players set #leaf_calls fc_probe 0
scoreboard players set #nested_val fc_probe 0
scoreboard players set #fork_leaf_val fc_probe 0

summon armor_stand 10 70 10 {Tags:["fc_e_leaf_agent"]}
summon armor_stand 20 70 20 {Tags:["fc_e_leaf_agent"]}
summon armor_stand 30 70 30 {Tags:["fc_e_leaf_agent"]}
