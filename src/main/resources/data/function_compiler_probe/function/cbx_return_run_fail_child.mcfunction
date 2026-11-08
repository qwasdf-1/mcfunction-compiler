# Child for the return-run/nested fail cells: two adds then a fail, with a
# pending fused tail that must never run.
scoreboard players add #fcprobe fc_probe 10
scoreboard players add #fcprobe fc_probe 20
return fail
scoreboard players add #fcprobe fc_probe 100
scoreboard players add #fcprobe fc_probe 100
