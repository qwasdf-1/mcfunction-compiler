# QUOTA-009: fork selection over a distance-filtered selector. The world
# spawn is pinned by the harness before this fixture, so the two tagged
# actors at distances 2 and 10 from it give exactly one match for
# distance=..3: the fork adds 100 once (101), separating the filtered subset
# from no match (1) and from both matching (201).
scoreboard players add #fcprobe fc_probe 1
execute as @e[tag=fc_fork_subset,distance=..3,limit=2,sort=nearest] run scoreboard players add #fcprobe fc_probe 100
