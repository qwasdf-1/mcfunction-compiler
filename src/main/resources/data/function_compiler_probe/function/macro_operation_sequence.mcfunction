$scoreboard players set #op_macro_a fc_probe $(a)
$scoreboard players set #op_macro_b fc_probe $(b)
scoreboard players operation #op_macro_a fc_probe += #op_macro_b fc_probe
scoreboard players operation #op_macro_a fc_probe *= #op_macro_b fc_probe
