# Coverage row ST-06, second half: `item modify` through the
# StateMachineCommand wrap (ItemCommandParser wraps every command whose class
# nest-host is ItemCommands). The `item replace` slot edges live in
# state_item_slot_edges; this fixture covers the modify half, which needed a
# confirmed 26.3 item-modifier id before it could be tested at all.
#
# 26.3 facts, read from the pinned vanilla server rather than assumed:
# the minecraft:item_modifier registry ships no built-in modifiers - every
# id is datapack-defined at data/<namespace>/item_modifier/<name>.json, as a
# single JSON object whose loot function is keyed by `type` (the array form
# and the pre-1.20.5 `function` key are rejected, and a malformed file is
# boot-fatal for the whole datapack). `item modify` returns result 1 on
# success, is idempotent in its result, and a store around it writes that
# result; a failing modify (a slot the target does not have) reports
# (success=false, result=0) to the store callback and does not abort the
# remaining function lines. An id the registry does not contain is validated
# at command-parse time - a function line referencing one fails the function
# load with "Can't find element ... in registry 'minecraft:item_modifier'",
# so the unknown-id edge is recorded here rather than fixture-able.
#
# Every case is a taken branch, so a truncated tail lowers the total instead
# of looking like an executed case:
#
# Case 1 (+1) resets the mainhand to a fresh diamond and branches on the
# stored `item modify` result 1. A skipped store leaves 0, so the branch is
# falsifiable.
#
# Case 2 (+2) branches on the modifier's observable effect: the mainhand
# stack must read diamond[count=5] after st06_set_count applied.
#
# Case 3 (+4) does the same on hotbar.8 with a fresh emerald. It is the
# final case and always fires on a complete run - the completion signal.
#
# expected 1,1,1 = 7
item replace entity FCProbe weapon.mainhand with minecraft:diamond
execute store result score #st06 fc_probe run item modify entity FCProbe weapon.mainhand function_compiler_probe:st06_set_count
execute if score #st06 fc_probe matches 1 run scoreboard players add #fcprobe fc_probe 1
execute if items entity FCProbe weapon.mainhand minecraft:diamond[count=5] run scoreboard players add #fcprobe fc_probe 2
item replace entity FCProbe hotbar.8 with minecraft:emerald
item modify entity FCProbe hotbar.8 function_compiler_probe:st06_set_count
execute if items entity FCProbe hotbar.8 minecraft:emerald[count=5] run scoreboard players add #fcprobe fc_probe 4
