$scoreboard players set #macro_cf fc_probe $(init)
$execute if score #macro_cf fc_probe matches 50.. run scoreboard players add #macro_cf fc_probe $(bonus)
scoreboard players add #macro_cf fc_probe 5
