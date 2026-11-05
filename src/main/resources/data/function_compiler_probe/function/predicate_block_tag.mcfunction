# Coverage row PR-03: a block predicate that names a block *tag* (`#ns:tag`)
# instead of a block id. Tag expansion must agree between the compiled and
# vanilla paths, so each tag is placed where its truth value is observable.
#
# Position 0 101 0 holds oak_planks: a member of #minecraft:planks and not of
# #minecraft:logs, with no member of #minecraft:buttons present. Position 0 102 0
# holds oak_log[axis=x] and exercises a tag combined with a state predicate.
#
# Each case adds its own power-of-two weight to #fcprobe, so the full-quota
# score reads as a binary string of the branch outcomes, most significant first:
# expected 1,0,1,1,0,0,1 = 89. The final case is a branch that is taken, which is
# what makes the declared value a completion signal: if the command quota ran out
# before the last case, the last digit would be missing and the comparison would
# fail. A fixture whose last case takes no branch cannot distinguish "the tail
# executed and was false" from "the tail never executed", and the first draft of
# this batch had exactly that flaw. Nine commands keep the run inside the quota
# sweep's top value of 16.
setblock 0 101 0 minecraft:oak_planks
setblock 0 102 0 minecraft:oak_log[axis=x]
execute if block 0 101 0 #minecraft:planks run scoreboard players add #fcprobe fc_probe 64
execute if block 0 101 0 #minecraft:logs run scoreboard players add #fcprobe fc_probe 32
execute unless block 0 101 0 #minecraft:logs run scoreboard players add #fcprobe fc_probe 16
execute if block 0 102 0 #minecraft:logs[axis=x] run scoreboard players add #fcprobe fc_probe 8
execute if block 0 101 0 #minecraft:buttons run scoreboard players add #fcprobe fc_probe 4
execute if block 0 102 0 #minecraft:logs[axis=z] run scoreboard players add #fcprobe fc_probe 2
execute unless block 0 101 0 #minecraft:buttons run scoreboard players add #fcprobe fc_probe 1
