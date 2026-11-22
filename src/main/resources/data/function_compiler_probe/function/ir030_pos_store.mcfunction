data modify entity @s data.frontier set value [{x:0,y:0,z:0}]
execute store result entity @s data.frontier[-1].x int 1 run data get entity @s Pos[0]
execute store result entity @s data.frontier[-1].y int 1 run data get entity @s Pos[1]
execute store result entity @s data.frontier[-1].z int 1 run data get entity @s Pos[2]
