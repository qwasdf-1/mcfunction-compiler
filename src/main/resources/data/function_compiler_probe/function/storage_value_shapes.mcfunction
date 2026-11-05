# Coverage rows DS-02 (compound/array/primitive values) and DC-02 (nested and
# indexed reads). The oracle folds storage values into #fcprobe through
# `execute store result score ... run data get storage` (no scale argument:
# 26.3 rejects one for score stores). A running weight gives each read its own
# decimal place, so the checksum identifies which read diverged. Run under the
# extended quota sweep (0-16).
scoreboard players set #ten fc_probe 10
scoreboard players set #weight fc_probe 1
data modify storage function_compiler_probe:covstate state set value {count:7,flag:1,list:[3,5,9],text:["ab","cd"]}
execute store result score #shape1 fc_probe run data get storage function_compiler_probe:covstate state.count
scoreboard players operation #fcprobe fc_probe = #shape1 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
data modify storage function_compiler_probe:covstate state.list[1] set value 50
execute store result score #shape2 fc_probe run data get storage function_compiler_probe:covstate state.list[1]
scoreboard players operation #shape2 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #shape2 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute store result score #shape3 fc_probe run data get storage function_compiler_probe:covstate state.text[0]
scoreboard players operation #shape3 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #shape3 fc_probe
