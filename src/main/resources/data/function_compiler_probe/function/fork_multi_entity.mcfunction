# Setup score markers
scoreboard players set #fork_zero fc_probe 0
scoreboard players set #fork_total fc_probe 0
scoreboard players set #fork_stored fc_probe 0

# Test 1: Zero matching entity selector
execute as @e[type=pig,tag=fc_nonexistent_pig] run scoreboard players add #fork_zero fc_probe 1

# Test 2: Multiple entity selector with ScoreAdd
execute as @e[tag=fc_fork_actor] run scoreboard players add #fork_total fc_probe 10

# Test 3: Multiple entity selector with downstream Transformation (at @s) and entity target (@s)
execute as @e[tag=fc_fork_actor] at @s run scoreboard players add @s fc_probe 5

# Test 4: Upstream execute store result over selector fork
execute store result score #fork_stored fc_probe as @e[tag=fc_fork_actor] run scoreboard players add @s fc_probe 1
