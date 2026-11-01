scoreboard players set @s fc_probe 2
scoreboard players set #s_self_val fc_probe 6
execute store result score @s fc_probe run scoreboard players operation #s_self_val fc_probe *= #s_self_val fc_probe
scoreboard players add @s fc_probe 4
