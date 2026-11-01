# Loaded block near 0, 0
setblock 0 64 0 minecraft:stone
# Unloaded chunk mutation (30000, 64, 30000 is far unloaded)
setblock 30000 64 30000 minecraft:stone
# Forceload a distant chunk, set block, remove forceload
forceload add 50 50 50 50
setblock 800 64 800 minecraft:diamond_block
forceload remove 50 50 50 50
scoreboard players add #boundary_res fc_probe 1
