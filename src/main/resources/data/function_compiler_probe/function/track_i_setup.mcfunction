scoreboard objectives add fc_probe dummy
scoreboard players set #has_item fc_probe 0
scoreboard players set #missing_item fc_probe 0
kill @e[tag=fc_i_agent]
summon armor_stand 0 64 0 {Tags:["fc_i_agent"]}
item replace entity @e[tag=fc_i_agent,limit=1] weapon.mainhand with diamond_sword
