# Coverage row SM-10: a scoreboard mutation with a multi-entity `@e[...]`
# selector must fan out to every matched entity, and a limited selector must
# not fan out past its cap.
#
# The four runner-prepared actors (tag fc_probe_actor) are seeded to 10, lose 3
# across the whole selector, and then lose 4 across a limited selector that must
# touch exactly two of them. The fold reads 2*3 + 2*7 = 20. That sum is reachable
# only if the full-selector remove applied to all four actors and the limited
# remove to exactly two: a full-selector-only mutation leaves 28, a
# limited-only mutation leaves 26, and a limited mutation that leaked to all
# four leaves 12.
#
# Both mutations and the fold live inside this function, so the Fabric arms
# execute them through the compiled path while vanilla runs them directly. The
# compiler declines selector operands on these families, so the claim this row
# makes is that the fallback fans out exactly as vanilla does.
scoreboard players set #mutation_sum fc_probe 0
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 10
scoreboard players remove @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 3
scoreboard players remove @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=2] fc_probe 4
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] run scoreboard players operation #mutation_sum fc_probe += @s fc_probe
