# Rider is generated as a nested horse passenger in the test; verify the relationship.
execute store success score #ride_success fc_ir030 run execute on vehicle if entity @s
function function_compiler_probe:ir030_pos_store
execute store result score #passenger_x fc_ir030 run data get entity @s data.frontier[-1].x
execute store result score #passenger_y fc_ir030 run data get entity @s data.frontier[-1].y
execute store result score #passenger_z fc_ir030 run data get entity @s data.frontier[-1].z
