# SCORE-007: an operation whose target selector matches no entity. A store
# result around the empty operation stores 0 and the bare operation leaves
# the objective untouched. The fold is store*10 + seed = 7, so an operation
# that created a target or stored a nonzero result separates immediately.
scoreboard players set #fcprobe fc_probe 0
scoreboard players set #fold_scale fc_probe 10
scoreboard players set #op_empty_seed fc_probe 7
scoreboard players set #op_empty_store fc_probe 0
execute store result score #op_empty_store fc_probe run scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_absent_marker] fc_probe += #op_empty_seed fc_probe
scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_absent_marker] fc_probe += #op_empty_seed fc_probe
scoreboard players operation #fcprobe fc_probe += #op_empty_store fc_probe
scoreboard players operation #fcprobe fc_probe *= #fold_scale fc_probe
scoreboard players operation #fcprobe fc_probe += #op_empty_seed fc_probe
