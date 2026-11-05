# Coverage row PR-05: an *item* predicate, including the `*[component]` wildcard
# form that matches any item carrying a component, a component-value predicate,
# and the pseudo-component `count`.
#
# The target is a chest at 0 105 0 whose container.0 holds a diamond sword
# carrying a custom_data component, prepared at the top of the fixture so the
# predicate shapes have observable truth values.
#
# 26.3 syntax note, confirmed against the vanilla server parser rather than
# assumed: a count *range* is not written `[count=1..]` or `[count=2..3]` (both
# fail to parse), and neither is `[count~1..]`. The range form is an SNBT object,
# `[count={"min":1,"max":3}]`. A plain `[count=1]` is an equality test.
#
# Each case adds its own power-of-two weight to #fcprobe, so the full-quota
# score reads as a binary string of the branch outcomes, most significant first:
# expected 1,0,1,1,1,0,0,1 = 185. The count range case is placed last precisely
# because it is a taken branch, so its weight doubles as the completion signal
# for the whole run. This fixture first carried twelve cases; the quota sweep's
# top value of 16 charged out mid-run and left three of them unexecuted in every
# arm, which the value comparison alone did not catch. Ten commands keep the run
# inside the quota sweep's top value of 16.
setblock 0 105 0 minecraft:chest
item replace block 0 105 0 container.0 with minecraft:diamond_sword[minecraft:custom_data={probe:1b}]
execute if items block 0 105 0 container.0 minecraft:diamond_sword run scoreboard players add #fcprobe fc_probe 128
execute if items block 0 105 0 container.0 minecraft:iron_sword run scoreboard players add #fcprobe fc_probe 64
execute if items block 0 105 0 container.0 #minecraft:swords run scoreboard players add #fcprobe fc_probe 32
execute if items block 0 105 0 container.0 *[minecraft:custom_data] run scoreboard players add #fcprobe fc_probe 16
execute if items block 0 105 0 container.0 minecraft:diamond_sword[minecraft:custom_data={probe:1b}] run scoreboard players add #fcprobe fc_probe 8
execute if items block 0 105 0 container.0 minecraft:diamond_sword[minecraft:custom_data={probe:2b}] run scoreboard players add #fcprobe fc_probe 4
execute if items block 0 105 0 container.1 minecraft:diamond_sword run scoreboard players add #fcprobe fc_probe 2
execute if items block 0 105 0 container.0 minecraft:diamond_sword[count={"min":1,"max":3}] run scoreboard players add #fcprobe fc_probe 1
