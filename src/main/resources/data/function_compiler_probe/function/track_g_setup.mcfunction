scoreboard objectives add fc_probe dummy
scoreboard players set #data_val fc_probe 0
scoreboard players set #data_scaled fc_probe 0
data modify storage fc:probe_g query set value {score:42, factor:10}
