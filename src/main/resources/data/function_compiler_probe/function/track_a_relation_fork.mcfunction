scoreboard players set #on_passengers fc_probe 0
scoreboard players set #on_vehicle fc_probe 0
scoreboard players set #no_vehicle fc_probe 0

# Test 1: execute as mount on passengers -> rider executes and adds 7 to #on_passengers
execute as @e[tag=fc_mount] on passengers run scoreboard players add #on_passengers fc_probe 7

# Test 2: execute as rider on vehicle -> mount executes and adds 13 to #on_vehicle
execute as @e[tag=fc_rider] on vehicle run scoreboard players add #on_vehicle fc_probe 13

# Test 3: execute as mount on vehicle -> mount has no vehicle, 0 executions
execute as @e[tag=fc_mount] on vehicle run scoreboard players add #no_vehicle fc_probe 1
