$scoreboard players set #macro_bw_a fc_probe $(base)
$scoreboard players add #macro_bw_a fc_probe $(step)
$scoreboard players set #macro_bw_b fc_probe $(mult)
scoreboard players operation #macro_bw_a fc_probe *= #macro_bw_b fc_probe
execute if score #macro_bw_a fc_probe matches 100.. run scoreboard players add #macro_bw_a fc_probe 50
