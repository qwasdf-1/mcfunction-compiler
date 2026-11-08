# QUOTA-009: fork selection over a distance-filtered selector that excludes
# every candidate. With the world spawn pinned by the harness, the two tagged
# actors at distances 10 and 20 are both outside distance=..5, so no branch
# runs and the score stays 1 across every fork cap - the no-match shape under
# a distance filter.
scoreboard players add #fcprobe fc_probe 1
execute as @e[tag=fc_fork_outside,distance=..5,limit=2,sort=nearest] run scoreboard players add #fcprobe fc_probe 100
