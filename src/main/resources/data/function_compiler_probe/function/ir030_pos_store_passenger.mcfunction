tag @s add ir030_passenger
ride @s mount @e[type=minecraft:horse,tag=ir030_vehicle,limit=1]
function function_compiler_probe:ir030_pos_store
execute store result score #passenger_x fc_ir030 run data get entity @s data.frontier[-1].x
execute store result score #passenger_y fc_ir030 run data get entity @s data.frontier[-1].y
execute store result score #passenger_z fc_ir030 run data get entity @s data.frontier[-1].z
