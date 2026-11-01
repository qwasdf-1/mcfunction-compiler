scoreboard players set @s fc_probe 100
scoreboard players set #c_limit fc_probe 50
execute as @s at @s positioned ~ ~ ~ if score @s fc_probe > #c_limit fc_probe run scoreboard players add @s fc_probe 15
execute as @s at @s store result score #stored_chain fc_probe run scoreboard players operation @s fc_probe += #c_limit fc_probe
scoreboard players add @s fc_probe 10
