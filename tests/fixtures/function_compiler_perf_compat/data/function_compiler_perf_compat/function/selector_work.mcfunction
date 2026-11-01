execute as @e[type=minecraft:zombie,tag=fc_perf_selector,tag=fc_perf_inside,x=0,y=99,z=0,dx=8,dy=2,dz=4,sort=nearest,limit=16] run scoreboard players add #selector_box fc_perf 1
execute as @e[type=minecraft:zombie,tag=fc_perf_selector,tag=fc_perf_inside,tag=!fc_perf_excluded,distance=..9,sort=furthest,limit=12] run scoreboard players add #selector_furthest fc_perf 1
execute as @e[type=minecraft:zombie,tag=fc_perf_selector,tag=fc_perf_far,sort=random,limit=8] run scoreboard players add #selector_random fc_perf 1
