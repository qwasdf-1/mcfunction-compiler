# Coverage row PR-04: a block predicate with an explicit block *state*
# (`block[prop=value,...]`). The oracle is state-property matching, so the
# observable shapes are a full-state predicate, a predicate naming only a subset
# of the block's properties, and a conjunction in which one named property is
# wrong.
#
# Position 0 103 0 holds oak_stairs[facing=north,waterlogged=false,half=bottom,
# shape=straight]. A partial predicate matches only the properties it names, so
# `[facing=north]` is true while `[waterlogged=true]` is false and
# `[facing=north,waterlogged=true]` is false.
#
# Each case adds its own power-of-two weight to #fcprobe, so the full-quota
# score reads as a binary string of the branch outcomes, most significant first:
# expected 1,0,1,0,0,0,1,1 = 163. As in the tag fixture, the final case is a
# branch that is taken, so the declared value doubles as a completion signal.
# Nine commands keep the run inside the quota sweep's top value of 16.
setblock 0 103 0 minecraft:oak_stairs[facing=north,waterlogged=false,half=bottom,shape=straight]
execute if block 0 103 0 minecraft:oak_stairs[facing=north,waterlogged=false,half=bottom,shape=straight] run scoreboard players add #fcprobe fc_probe 128
execute if block 0 103 0 minecraft:oak_stairs[waterlogged=true] run scoreboard players add #fcprobe fc_probe 64
execute if block 0 103 0 minecraft:oak_stairs[facing=north] run scoreboard players add #fcprobe fc_probe 32
execute if block 0 103 0 minecraft:oak_stairs[facing=north,waterlogged=true] run scoreboard players add #fcprobe fc_probe 16
execute if block 0 103 0 minecraft:stone run scoreboard players add #fcprobe fc_probe 8
execute if block 0 103 0 minecraft:oak_stairs[facing=south] run scoreboard players add #fcprobe fc_probe 4
execute unless block 0 103 0 minecraft:oak_stairs[facing=south] run scoreboard players add #fcprobe fc_probe 2
execute if block 0 103 0 minecraft:oak_stairs[facing=north,shape=straight] run scoreboard players add #fcprobe fc_probe 1
