scoreboard objectives add fc_probe dummy
scoreboard players set #effect_done fc_probe 0
kill @e[tag=fc_m_target]
summon armor_stand 0 64 0 {Tags:["fc_m_target"]}
