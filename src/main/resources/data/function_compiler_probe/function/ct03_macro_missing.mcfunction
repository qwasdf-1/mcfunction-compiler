# CT-03 helper: a macro function whose declared `absent` key is not supplied by
# the caller. Vanilla fails the expansion at the call, so no line here runs.
$scoreboard players add #fcprobe fc_probe $(step)
$scoreboard players add #fcprobe fc_probe $(absent)
