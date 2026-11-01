scoreboard players set #at_sum fc_probe 0
scoreboard players set #stored_at fc_probe 0
scoreboard players set #counter fc_probe 0

# Test 1: execute at @e[...]
execute at @e[tag=fc_spatial_a] run scoreboard players add #at_sum fc_probe 10

# Test 2: execute as @e[...] at @s positioned ~ ~1 ~
execute as @e[tag=fc_spatial_a] at @s positioned ~ ~1 ~ run scoreboard players add @s fc_probe 5

# Test 3: execute store result over execute at @e[...]
execute store result score #stored_at fc_probe at @e[tag=fc_spatial_a] run scoreboard players add #counter fc_probe 1
