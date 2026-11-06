# CT-03 helper: a macro function that mutates +10, then fails on a missing
# objective, then mutates +10 again. The completed first add must persist once.
$scoreboard players add #fcprobe fc_probe $(step)
scoreboard players add #fcprobe fc_missing 1
$scoreboard players add #fcprobe fc_probe $(step)
