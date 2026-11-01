scoreboard objectives add fc_probe dummy
scoreboard players set #store_target fc_probe 0
scoreboard players set #val_copied fc_probe 0
scoreboard players set #stored_int fc_probe 0
scoreboard players set #stored_success fc_probe 0

data modify storage fc:track_d_src payload set value {counter: 42, label: "origin"}
data remove storage fc:track_d_dst payload
data remove storage fc:track_d_store root
