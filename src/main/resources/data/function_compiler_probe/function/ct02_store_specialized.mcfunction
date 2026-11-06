# Coverage row CT-02: result/success propagation around specialized operations.
#
# The existing store fixtures wrap scoreboard adds and operations; this one
# wraps two other specialized families: a data `get` and a state-machine
# `setblock`. The stored values are then folded into #fcprobe as power-of-two
# weights, so a store that writes the wrong callback value flips exactly one
# digit.
#
# `data get` is the case that separates result from success: its result is the
# stored value 7, while its success flag would be 1. A store that wrote success
# in place of result therefore reads 1 and fails the 7 branch. `setblock`
# asserts the success side, which is 1 for an accepted change.
#
# The air reset is not decoration. 26.3 `setblock` reports success 0 for an
# unchanged block ("Could not set the block"), measured directly: a second
# identical setblock stored 0. Without the reset, the fixture's second and later
# quota iterations would assert the unchanged-block failure path instead of the
# accepted path. The reset also means every iteration exercises a real change.
#
# A first draft also wrapped `effect give` under `execute store success`. It
# reached only 32 of its declared 48 by quota 16: the effect store and its
# branch cost more queue entries than a single-position setblock, and the case
# never executed. The ST-04 fixture already asserts the refused-setblock
# success side (0), so this fixture covers the accepted side rather than
# repeating the failure.
#
# expected 1,1 = 3.
data modify storage function_compiler_probe:ct02 value set value 7
setblock 0 120 0 minecraft:air
execute store result score #ct02_data fc_probe run data get storage function_compiler_probe:ct02 value
execute store success score #ct02_setblock fc_probe run setblock 0 120 0 minecraft:stone
execute if score #ct02_data fc_probe matches 7 run scoreboard players add #fcprobe fc_probe 2
execute if score #ct02_setblock fc_probe matches 1 run scoreboard players add #fcprobe fc_probe 1
