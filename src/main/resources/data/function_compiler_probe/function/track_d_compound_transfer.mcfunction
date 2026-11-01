data modify storage fc:track_d_dst payload set from storage fc:track_d_src payload
execute store result storage fc:track_d_store root.int_val int 1 run scoreboard players add #store_target fc_probe 15
execute store result storage fc:track_d_store root.scaled_val double 0.5 run scoreboard players add #store_target fc_probe 20
execute store success storage fc:track_d_store root.success_val byte 1 run scoreboard players add #store_target fc_probe 5

execute store result score #val_copied fc_probe run data get storage fc:track_d_dst payload.counter
execute store result score #stored_int fc_probe run data get storage fc:track_d_store root.int_val
execute store result score #stored_success fc_probe run data get storage fc:track_d_store root.success_val
