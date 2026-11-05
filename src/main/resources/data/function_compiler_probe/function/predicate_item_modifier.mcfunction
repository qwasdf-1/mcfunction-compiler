# Coverage row MO-07: the item predicate used as an execute *modifier*, i.e. a
# stack predicate sitting inside a modifier chain rather than naming its target
# in isolation. The cases put the predicate behind an `unless`, in a conjunction
# with a block predicate, and in a conjunction whose second conjunct fails.
#
# The target is a chest at 0 107 0 whose container.0 holds a diamond sword with
# a custom_data component, prepared at the top of the fixture. The chest block
# itself is the conjunct the chain cases use, so the fixture needs no entity: an
# earlier draft of this fixture equipped a summoned armor stand, but the entity
# was not selectable in the scratch server used to confirm the grammar, and an
# entity-dependent fixture would also accumulate stands across the seventeen
# quota invocations.
#
# Each case adds its own power-of-two weight to #fcprobe, so the full-quota
# score reads as a binary string of the branch outcomes, most significant first:
# expected 1,1,0,1 = 13. The final case is a taken branch, so its weight doubles
# as the completion signal. Charge-cost note, learned by observation: an
# `execute if items` line and a chain of two predicates each cost noticeably more
# of the command quota than a plain scoreboard line, so this fixture carries four
# cases rather than the nine its first draft had; a longer list leaves its tail
# unexecuted at quota 16 in every arm. Six commands keep the run inside the
# quota sweep's top value of 16.
setblock 0 107 0 minecraft:chest
item replace block 0 107 0 container.0 with minecraft:diamond_sword[minecraft:custom_data={probe:1b}]
execute if items block 0 107 0 container.0 *[minecraft:custom_data] run scoreboard players add #fcprobe fc_probe 8
execute if block 0 107 0 minecraft:chest if items block 0 107 0 container.0 minecraft:diamond_sword run scoreboard players add #fcprobe fc_probe 4
execute if block 0 107 0 minecraft:chest if items block 0 107 0 container.0 minecraft:iron_sword run scoreboard players add #fcprobe fc_probe 2
execute unless items block 0 107 0 container.0 minecraft:iron_sword run scoreboard players add #fcprobe fc_probe 1
