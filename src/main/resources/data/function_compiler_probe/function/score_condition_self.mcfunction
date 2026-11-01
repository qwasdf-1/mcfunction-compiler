scoreboard players set @s fc_probe 0
scoreboard players set #c_self_cond fc_probe 15
execute if score @s fc_probe < #c_self_cond fc_probe run scoreboard players add @s fc_probe 10
execute unless score @s fc_probe matches 5..20 run scoreboard players add @s fc_probe 100
execute if score @s fc_probe matches 10..15 run scoreboard players add @s fc_probe 25
scoreboard players add @s fc_probe 5
