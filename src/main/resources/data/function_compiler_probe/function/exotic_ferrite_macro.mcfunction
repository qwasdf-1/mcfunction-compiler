$scoreboard players set #ferrite_m1 fc_probe $(val1)
$scoreboard players set #ferrite_m2 fc_probe $(val2)
scoreboard players operation #ferrite_sum fc_probe = #ferrite_m1 fc_probe
scoreboard players operation #ferrite_sum fc_probe += #ferrite_m2 fc_probe
