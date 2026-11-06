# Coverage row ST-03: `effect give/clear <target> <effect> ...` at the
# amplifier and duration edges, and the `clear` half of the family.
#
# The oracle is the entity's own data, read back with `data get entity` and
# folded into #fcprobe as power-of-two weights. The four runner-prepared actors
# are used because the harness keeps them loaded and tagged, and `give`/`clear`
# are issued without `limit` so they apply to every actor, while each read uses
# `limit=1` because a data path resolves against a single entity.
#
# 26.3 data-path note, read from the entity rather than assumed: an entity's
# active effects live at `active_effects`, in snake case, and each element is
# `{duration: <ticks>, show_icon: 1b, amplifier: <byte>, id: "minecraft:<name>"}`.
# The pre-1.20.5 path `ActiveEffects[0].Amplifier` matches nothing.
#
# 26.3 ordering note, read from the entity rather than assumed: the list is
# *sorted* by effect id, not ordered by application, and a re-given effect
# cannot have its amplifier lowered. Both of those forced this fixture's shape.
# An earlier draft gave speed and slowness before reading and then asserted
# index positions; either digit could have been produced by the sort order
# rather than by a correct read, and with more than one effect active there is
# no line that says "I am reading the effect I just gave". This fixture
# therefore keeps exactly one effect active at a time, so `active_effects[0]`
# means exactly the effect just given.
#
# That constraint costs lines, and the quota sweep charges each command, so the
# draft that cleared between every case ran out of budget before its last case
# executed - the map never reached its declared value, which is the failure
# this fixture's header documents for the multiply-chain predicate row. Reading
# the amplifier and the duration from the *same* effect back to back removes a
# whole clear-and-give group, and the trailing `effect clear` does double duty
# as the final case's setup.
#
# Case 1 (+64) is the amplifier edge. The amplifier is stored as a *signed*
# byte, so the command's maximum amplifier of 255 reads back as -1. The case
# asserts -1 rather than 255, because that is what the entity data holds, and a
# specialization that compared the command argument against the stored value
# would fail exactly here.
#
# Case 2 (+32) is the duration edge on the same effect: 600 seconds is stored as
# 12000 ticks, so the seconds-to-ticks conversion is observable in the score.
# Both cases use the same long duration for a second reason: an earlier draft
# gave the effects a 1-second duration and both the compiled and the vanilla
# arms produced different scores on different runs, because the effect expired
# part-way through the fixture. A 600-second duration cannot lapse between the
# `give` and the read.
#
# Case 3 (+16) is `effect clear`. After the clear the `active_effects[0]` path
# no longer resolves, which is asserted with `execute unless data` rather than
# by reading a sentinel, so the claim is "the element is gone" instead of "the
# element holds some value I chose".
#
# There is deliberately no `effect clear` at the start, and the reason was
# measured rather than assumed. If a low-quota sweep is truncated after the
# `give`, the next sweep re-gives the identical effect, which changes nothing:
# a focused probe ran the fixture against one and produced the same 112. Note
# that this only holds because the leftover is *identical*. Vanilla also refuses
# to shorten an active effect's duration, so a leftover with a longer duration
# keeps it and case 2 would read the longer value - the probe produced 80 in
# that situation. This fixture can never leave a longer duration behind, because
# every sweep gives the same effect at the same duration. The trailing clear is
# the last branch, so a truncated run is distinguishable from a run in which the
# clear itself was refused.
effect give @e[type=minecraft:armor_stand,tag=fc_probe_actor] minecraft:speed 600 255
execute store result score #effect_ampl fc_probe run data get entity @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=1] active_effects[0].amplifier
execute if score #effect_ampl fc_probe matches -1 run scoreboard players add #fcprobe fc_probe 64
execute store result score #effect_dur fc_probe run data get entity @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=1] active_effects[0].duration
execute if score #effect_dur fc_probe matches 12000 run scoreboard players add #fcprobe fc_probe 32
effect clear @e[type=minecraft:armor_stand,tag=fc_probe_actor]
execute unless data entity @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=1] active_effects[0].amplifier run scoreboard players add #fcprobe fc_probe 16
