# CT-01 helper: a second frame with the same region/boundary/region/return
# shape, reached through `return run` so the outer frame's pending tail is
# discarded as well.
scoreboard players add #fcprobe fc_probe 100
say ct01-child-boundary
scoreboard players add #fcprobe fc_probe 200
return 7
scoreboard players add #fcprobe fc_probe 1000
