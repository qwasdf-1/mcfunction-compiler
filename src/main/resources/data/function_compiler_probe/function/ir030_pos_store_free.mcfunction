tag @s add ir030_free
function function_compiler_probe:ir030_pos_store
execute store result score #free_x fc_ir030 run data get entity @s data.frontier[-1].x
execute store result score #free_y fc_ir030 run data get entity @s data.frontier[-1].y
execute store result score #free_z fc_ir030 run data get entity @s data.frontier[-1].z
