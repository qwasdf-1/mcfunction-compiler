execute if items entity @e[tag=fc_i_agent,limit=1] weapon.mainhand diamond_sword run scoreboard players set #has_item fc_probe 1
execute unless items entity @e[tag=fc_i_agent,limit=1] weapon.mainhand iron_sword run scoreboard players set #missing_item fc_probe 2
