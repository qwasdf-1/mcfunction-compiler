tag @s add ir030_nonmarker
data modify entity @s data.frontier set value [{x:0,y:0,z:0}]
function function_compiler_probe:ir030_pos_store
execute store result score #nonmarker_x fc_ir030 run data get entity @s data.frontier[-1].x
execute store result score #nonmarker_y fc_ir030 run data get entity @s data.frontier[-1].y
execute store result score #nonmarker_z fc_ir030 run data get entity @s data.frontier[-1].z
