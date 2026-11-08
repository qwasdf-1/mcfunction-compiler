# SCORE-007: a failing operation (divide by zero) under both execute-store
# callback contexts. The failed operation stores 0 into the result callback
# and 0 into the success callback, and the target keeps its seeded value of 7.
# The fold is result_store*10000 + success_store*100 + target = 7.
scoreboard players set #fcprobe fc_probe 0
scoreboard players set #fold_scale fc_probe 100
scoreboard players set #op_div_target fc_probe 7
scoreboard players set #op_div_zero fc_probe 0
scoreboard players set #op_div_store_result fc_probe 0
scoreboard players set #op_div_store_success fc_probe 0
execute store result score #op_div_store_result fc_probe run scoreboard players operation #op_div_target fc_probe /= #op_div_zero fc_probe
scoreboard players operation #fcprobe fc_probe += #op_div_store_result fc_probe
scoreboard players operation #fcprobe fc_probe *= #fold_scale fc_probe
execute store success score #op_div_store_success fc_probe run scoreboard players operation #op_div_target fc_probe /= #op_div_zero fc_probe
scoreboard players operation #fcprobe fc_probe += #op_div_store_success fc_probe
scoreboard players operation #fcprobe fc_probe *= #fold_scale fc_probe
scoreboard players operation #fcprobe fc_probe += #op_div_target fc_probe
