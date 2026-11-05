# Coverage rows SS-03 (an execute store result/success score target that does
# not yet exist) and SS-04 (a store under a modifier chain). Both stores write
# into the initially-absent #fresh_store holder around a data command whose
# result is a known value, and the second runs inside an `as @e` context
# modifier, so a wrongly folded modifier shows as a different score.
scoreboard players set #ten fc_probe 10
scoreboard players set #weight fc_probe 1
execute store result score #fresh_store fc_probe run data get storage function_compiler_probe:covstore valid
scoreboard players operation #fcprobe fc_probe = #fresh_store fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute as @e[tag=fc_cond_actor] store result score #fresh_store fc_probe run data get storage function_compiler_probe:covstore valid
scoreboard players operation #fcprobe fc_probe += #fresh_store fc_probe
