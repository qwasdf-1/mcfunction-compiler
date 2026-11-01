scoreboard players set #s_counter fc_probe 5
execute store result score #s_stored_res fc_probe run scoreboard players add #s_counter fc_probe 3
execute store success score #s_stored_succ fc_probe run scoreboard players add #s_counter fc_probe 2
execute store result score #s_stored_calc fc_probe run scoreboard players operation #s_counter fc_probe *= #s_stored_res fc_probe
scoreboard players operation #s_final fc_probe = #s_counter fc_probe
scoreboard players add #s_final fc_probe 100
