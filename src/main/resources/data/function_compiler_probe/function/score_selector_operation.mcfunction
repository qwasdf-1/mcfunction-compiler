# Coverage row SO-07: a scoreboard *operation* whose target is a multi-entity
# selector fans out, and an operation onto an absent target creates the score
# rather than dropping it.
#
# Two folded phases, each shifted one decimal place by #fold_scale so a single
# read separates them. Phase one seeds the four actors to 4 and adds a fake
# holder of 10 through the selector, so the fan-out reads 4*14 = 56. Phase two
# resets the actors to absent and assigns a creation seed of 9 through the same
# selector, so the fan-out reads 4*9 = 36: an operation that dropped absent
# targets would read 0, and one that only touched a single actor would read 9.
#
# The declared total is 56*100 + 36 = 5636.
scoreboard players set #operation_sum fc_probe 0
scoreboard players set #fold_scale fc_probe 100
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 4
scoreboard players set #operation_source fc_probe 10
scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe += #operation_source fc_probe
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] run scoreboard players operation #operation_sum fc_probe += @s fc_probe
scoreboard players operation #operation_sum fc_probe *= #fold_scale fc_probe
scoreboard players reset @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
scoreboard players set #creation_seed fc_probe 9
scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe = #creation_seed fc_probe
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] run scoreboard players operation #operation_sum fc_probe += @s fc_probe
