scoreboard players set #c_res fc_probe 0
scoreboard players set #c_cond fc_probe 10
scoreboard players set #c_cmp fc_probe 10
execute if score #c_cond fc_probe = #c_cmp fc_probe run scoreboard players add #c_res fc_probe 1
execute unless score #c_cond fc_probe = #c_cmp fc_probe run scoreboard players add #c_res fc_probe 100
execute if score #c_cond fc_probe < #c_cmp fc_probe run scoreboard players add #c_res fc_probe 100
execute if score #c_cond fc_probe <= #c_cmp fc_probe run scoreboard players add #c_res fc_probe 2
execute if score #c_cond fc_probe >= #c_cmp fc_probe run scoreboard players add #c_res fc_probe 4
execute if score #c_cond fc_probe matches 5..15 run scoreboard players add #c_res fc_probe 8
execute unless score #c_cond fc_probe matches 20..30 run scoreboard players add #c_res fc_probe 16
scoreboard players operation #c_res fc_probe += #c_cond fc_probe
