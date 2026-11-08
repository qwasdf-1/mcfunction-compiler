# QUOTA-009: fork selection over a type-filtered selector with a
# differently-typed decoy sharing the same tag. Only the armor stands may
# match, so the fork adds 10 per selected stand and the decoy never
# contributes.
scoreboard players add #fcprobe fc_probe 1
execute as @e[type=minecraft:armor_stand,tag=fc_fork_type,limit=2,sort=nearest] run scoreboard players add #fcprobe fc_probe 10
