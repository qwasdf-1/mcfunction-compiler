# Coverage row SM-12: a mutation wrapped in a modifier chain must dispatch with
# the modifier's context, and a per-actor condition inside that chain must be
# evaluated once per actor rather than once for the whole chain.
#
# Three folded phases, each shifted one decimal place by #fold_scale. Two of the
# four actors are seeded to 99 and the other two to 7, so a per-actor condition
# counts exactly the two high actors (reads 2, not 1 and not 4); an `at @s`
# context modifier adds 100 per actor (reads 400); and the negated condition
# counts the two low actors (reads 20). A chain that evaluated its condition in
# a single context would report 1 or 0, and one that lost the `at` context would
# still add per actor but would lose the per-actor selector resolution - the
# sum separates all three.
#
# The declared total is (2*100 + 400)*100 + 20 = 60020.
scoreboard players set #modifier_sum fc_probe 0
scoreboard players set #fold_scale fc_probe 100
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 7
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=2] fc_probe 99
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] if score @s fc_probe matches 99.. run scoreboard players add #modifier_sum fc_probe 1
scoreboard players operation #modifier_sum fc_probe *= #fold_scale fc_probe
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] at @s run scoreboard players add #modifier_sum fc_probe 100
scoreboard players operation #modifier_sum fc_probe *= #fold_scale fc_probe
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] unless score @s fc_probe matches 99.. run scoreboard players add #modifier_sum fc_probe 10
