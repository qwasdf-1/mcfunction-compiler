scoreboard players set @s leaf_score 0
function function_compiler_probe:track_e_child
execute as @e[tag=fc_e_leaf_agent] run function function_compiler_probe:track_e_child
execute store result score #fork_leaf_val fc_probe run scoreboard players get @s leaf_score
