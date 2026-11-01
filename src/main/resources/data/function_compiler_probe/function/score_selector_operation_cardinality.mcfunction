scoreboard players operation #selector_operation_target fc_probe += @e[type=minecraft:armor_stand,tag=fc_no_selector_matches] fc_probe
scoreboard players operation #selector_operation_target fc_probe += @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
scoreboard players add #selector_operation_followup fc_probe 7
