data modify entity @s data.frontier set value [{x:7,y:8,z:9}]
execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Missing[0]
execute store result score #missing_x fc_ir030 run data get entity @s data.frontier[-1].x
execute store result score #missing_y fc_ir030 run data get entity @s data.frontier[-1].y
execute store result score #missing_z fc_ir030 run data get entity @s data.frontier[-1].z
