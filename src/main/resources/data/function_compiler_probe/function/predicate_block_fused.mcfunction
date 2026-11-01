setblock 0 100 0 minecraft:stone
scoreboard players set #pred_b fc_probe 0
execute if block 0 100 0 minecraft:stone run scoreboard players add #pred_b fc_probe 15
execute unless block 0 100 0 minecraft:stone run scoreboard players add #pred_b fc_probe 100
execute if block 0 100 0 minecraft:dirt run scoreboard players add #pred_b fc_probe 200
execute unless block 0 100 0 minecraft:dirt run scoreboard players add #pred_b fc_probe 35
execute positioned 0 100 0 if block ~ ~ ~ minecraft:stone run scoreboard players add #pred_b fc_probe 20
