# Coverage row ST-06 / matrix case STATE-004: the slot edges through
# `item modify` with the confirmed datapack modifier
# function_compiler_probe:st06_set_count (sets count=5; batch 10 measured
# that the 26.3 minecraft:item_modifier registry ships no built-in
# modifiers, so every id is datapack-defined).
#
# The oracle is the probe player's own inventory read back with
# `execute if items`, folded as distinct powers of two: hotbar.0 (+64),
# the last hotbar slot hotbar.8 (+32), a different slot group
# weapon.offhand (+16), and the empty slot that must not match (+1).
# hotbar.5 is cleared first so the empty-slot case is deterministic, and
# the modify on the empty slot is a taken branch in its own right: a
# modifier on a slot with no item fails without aborting the remaining
# function lines (ST-06's measured failure edge), so the read-back must
# still not match.
item replace entity FCProbe hotbar.5 with air
item replace entity FCProbe hotbar.0 with minecraft:diamond
item modify entity FCProbe hotbar.0 function_compiler_probe:st06_set_count
execute if items entity FCProbe hotbar.0 minecraft:diamond[count=5] run scoreboard players add #fcprobe fc_probe 64
item replace entity FCProbe hotbar.8 with minecraft:emerald 3
item modify entity FCProbe hotbar.8 function_compiler_probe:st06_set_count
execute if items entity FCProbe hotbar.8 minecraft:emerald[count=5] run scoreboard players add #fcprobe fc_probe 32
item replace entity FCProbe weapon.offhand with minecraft:arrow
item modify entity FCProbe weapon.offhand function_compiler_probe:st06_set_count
execute if items entity FCProbe weapon.offhand minecraft:arrow[count=5] run scoreboard players add #fcprobe fc_probe 16
item modify entity FCProbe hotbar.5 function_compiler_probe:st06_set_count
execute unless items entity FCProbe hotbar.5 minecraft:diamond[count=5] run scoreboard players add #fcprobe fc_probe 1
