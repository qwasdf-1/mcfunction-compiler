# Coverage row ST-06: gameplay item commands (`item replace/modify`) at the
# slot edges.
#
# The oracle is the player's own inventory, read back with
# `execute if items` and folded into #fcprobe as power-of-two weights. The probe
# player is present in every arm of the runtime probe, so the read-back does not
# depend on a summoned entity. hotbar.0 is the first valid slot, hotbar.8 is the
# last, weapon.offhand is a different slot group, and hotbar.5 is cleared first
# so the empty-slot case is deterministic rather than accidental.
#
# Cases: a plain item in hotbar.0 (+64), a counted stack in hotbar.8 (+32), the
# offhand slot (+16), and an empty slot that must not match (+1). The item
# predicates used to read the slots back are the same shape the predicate batch
# validated, so a slot that resolved wrongly would show up as a flipped digit.
#
# Not covered here, and recorded as such at the time: `item modify` needed an
# item-modifier id from the 26.3 `minecraft:item_modifier` registry. The modify
# half since closed with a confirmed datapack-defined id - see
# st06_item_modify, which also records the measured registry semantics.
item replace entity FCProbe hotbar.5 with air
item replace entity FCProbe hotbar.0 with minecraft:diamond
execute if items entity FCProbe hotbar.0 minecraft:diamond run scoreboard players add #fcprobe fc_probe 64
item replace entity FCProbe hotbar.8 with minecraft:emerald 7
execute if items entity FCProbe hotbar.8 minecraft:emerald[count=7] run scoreboard players add #fcprobe fc_probe 32
item replace entity FCProbe weapon.offhand with minecraft:shield
execute if items entity FCProbe weapon.offhand minecraft:shield run scoreboard players add #fcprobe fc_probe 16
execute unless items entity FCProbe hotbar.5 minecraft:diamond run scoreboard players add #fcprobe fc_probe 1
