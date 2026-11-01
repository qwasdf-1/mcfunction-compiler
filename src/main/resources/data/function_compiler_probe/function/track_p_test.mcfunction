item replace entity @e[tag=fc_p_target,limit=1] weapon.mainhand with iron_sword
execute if items entity @e[tag=fc_p_target,limit=1] weapon.mainhand iron_sword run scoreboard players set #item_done fc_probe 1
