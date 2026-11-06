# Coverage row ST-04: `setblock <pos> <block>[state] [mode]`, including the
# out-of-world fallback the row names.
#
# The oracle is the block state itself, read back with `execute if block` and
# folded into #fcprobe as power-of-two weights. Position 0 111 0 takes a plain
# block, 0 112 0 takes a state-qualified block, 0 113 1 is the `keep` mode: a
# diamond block is placed and a `keep` replacement is then refused, so the block
# must still be diamond and the case is only reachable if the mode was honoured.
# The last case is the row's fallback condition: `setblock` at y=-70, below the
# world bottom, is refused, and the position must read air.
#
# The last case is the row's fallback condition. Two 26.3 behaviours were read
# from the server rather than assumed. A refused `setblock` does *not* abort the
# rest of the function, so the commands after it still run. And `execute store
# success score` around the refused setblock writes 0, while the same store
# around an accepted setblock writes 1 - so the refusal itself is observable in
# a scoreboard, which is what the case asserts. Note that `execute if block` at
# an out-of-world position aborts the whole command with an error, so it cannot
# be used as a negative predicate there.
setblock 0 111 0 minecraft:stone
execute if block 0 111 0 minecraft:stone run scoreboard players add #fcprobe fc_probe 64
setblock 0 112 0 minecraft:oak_log[axis=x]
execute if block 0 112 0 minecraft:oak_log[axis=x] run scoreboard players add #fcprobe fc_probe 32
setblock 0 113 1 minecraft:diamond_block
setblock 0 113 1 minecraft:gold_block keep
execute if block 0 113 1 minecraft:diamond_block run scoreboard players add #fcprobe fc_probe 16
scoreboard players set #setblock_success fc_probe 1
execute store success score #setblock_success fc_probe run setblock 0 -70 0 minecraft:stone
execute if score #setblock_success fc_probe matches 0 run scoreboard players add #fcprobe fc_probe 1
