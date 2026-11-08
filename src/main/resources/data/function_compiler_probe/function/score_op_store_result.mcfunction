# SCORE-007: a scoreboard operation under the two execute-store callback
# contexts. The *= operation's stored result is 12 (the operation's new
# target value) and the += operation's stored success is 1. The fold is
# store_result*10000 + store_success*100 + target = 12*10000 + 1*100 + 16
# = 120116, so one read separates the result store from the success store
# from the target's applied value.
scoreboard players set #fcprobe fc_probe 0
scoreboard players set #fold_scale fc_probe 100
scoreboard players set #op_target fc_probe 3
scoreboard players set #op_source fc_probe 4
scoreboard players set #op_store_result fc_probe 0
scoreboard players set #op_store_success fc_probe 0
execute store result score #op_store_result fc_probe run scoreboard players operation #op_target fc_probe *= #op_source fc_probe
scoreboard players operation #fcprobe fc_probe += #op_store_result fc_probe
scoreboard players operation #fcprobe fc_probe *= #fold_scale fc_probe
execute store success score #op_store_success fc_probe run scoreboard players operation #op_target fc_probe += #op_source fc_probe
scoreboard players operation #fcprobe fc_probe += #op_store_success fc_probe
scoreboard players operation #fcprobe fc_probe *= #fold_scale fc_probe
scoreboard players operation #fcprobe fc_probe += #op_target fc_probe
