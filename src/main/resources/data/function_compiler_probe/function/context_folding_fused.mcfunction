scoreboard players set @s fc_probe 10
scoreboard players set #fold_bonus fc_probe 5
execute as @s run scoreboard players add @s fc_probe 2
execute as @s at @s run scoreboard players add @s fc_probe 3
execute as @s at @s positioned ~ ~1 ~ run scoreboard players add @s fc_probe 4
execute as @s at @s rotated ~ 0 run scoreboard players add @s fc_probe 5
execute as @s at @s anchored feet run scoreboard players add @s fc_probe 6
execute as @s positioned as @s run scoreboard players add @s fc_probe 7
execute as @s rotated as @s run scoreboard players add @s fc_probe 8
scoreboard players operation @s fc_probe += #fold_bonus fc_probe
