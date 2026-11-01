$scoreboard players set #mb_acc fc_probe $(init)
$scoreboard players add #mb_acc fc_probe $(step)
$scoreboard players add #mb_acc fc_probe $(step)
$scoreboard players add #mb_acc fc_probe $(step)
$scoreboard players remove #mb_acc fc_probe $(sub)
$scoreboard players remove #mb_acc fc_probe $(sub)
scoreboard players add #mb_acc fc_probe 10
scoreboard players add #mb_acc fc_probe 20
scoreboard players set #mb_temp fc_probe 5
scoreboard players operation #mb_acc fc_probe += #mb_temp fc_probe
scoreboard players reset #mb_temp fc_probe
