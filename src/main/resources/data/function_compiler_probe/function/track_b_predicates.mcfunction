execute if entity @e[tag=fc_track_b_tag_a] run scoreboard players add #pred_if_ent fc_probe 10
execute unless entity @e[tag=fc_track_b_tag_missing] run scoreboard players add #pred_unless_ent fc_probe 20
execute if entity @e[tag=fc_track_b_tag_missing] run scoreboard players add #pred_if_missing fc_probe 999
execute unless entity @e[tag=fc_track_b_tag_a] run scoreboard players add #pred_unless_present fc_probe 999

execute if predicate function_compiler_probe:always_true run scoreboard players add #pred_if_pred fc_probe 30
execute unless predicate function_compiler_probe:always_false run scoreboard players add #pred_unless_pred fc_probe 40
execute if predicate function_compiler_probe:always_false run scoreboard players add #pred_fail_pred fc_probe 999
execute unless predicate function_compiler_probe:always_true run scoreboard players add #pred_fail_unless_pred fc_probe 999

execute as @e[tag=fc_track_b_tag_a] if entity @s run scoreboard players add #pred_self fc_probe 5
