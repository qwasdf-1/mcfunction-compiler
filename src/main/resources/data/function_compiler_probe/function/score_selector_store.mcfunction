# Coverage row SM-13: a mutation under `execute store result/success` whose
# target is a multi-entity selector must write into every matched entity,
# creating the score where the target has none.
#
# The actors' scores are reset first so the store target is genuinely absent,
# the stored value is established in storage so the inner command's result is
# known, and the fold reads 4*5 = 20. A store that wrote to a single actor
# reads 5, one that left the targets absent reads 0, and one that wrote the
# success flag instead of the result reads 4 - so the sum separates the result
# store from the success store and from a partial fan-out.
scoreboard players set #store_sum fc_probe 0
data modify storage function_compiler_probe:covstore valid set value 5
scoreboard players reset @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
execute store result score @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe run data get storage function_compiler_probe:covstore valid
execute as @e[type=minecraft:armor_stand,tag=fc_probe_actor] run scoreboard players operation #store_sum fc_probe += @s fc_probe
