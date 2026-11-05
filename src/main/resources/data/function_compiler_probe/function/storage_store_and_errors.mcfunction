# Coverage rows DS-04 (data get on a malformed/absent path) and DS-05
# (execute store result/success around a data command). A successful read
# establishes a nonzero checksum first; the failing reads then must record
# success 0 and must not move the result store, so any wrong specialization
# shows up as a changed score. Run under the extended quota sweep (0-16).
scoreboard players set #ten fc_probe 10
scoreboard players set #weight fc_probe 1
data modify storage function_compiler_probe:covstore valid set value 5
execute store result score #err1 fc_probe run data get storage function_compiler_probe:covstore valid
scoreboard players operation #fcprobe fc_probe = #err1 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute store success score #err2 fc_probe run data get storage function_compiler_probe:covabsent nothing.nested
scoreboard players operation #fcprobe fc_probe += #err2 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute store result score #err3 fc_probe run data get storage function_compiler_probe:covabsent nothing.nested
scoreboard players operation #err3 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #err3 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute store result score #err4 fc_probe run data get storage function_compiler_probe:covstore valid
scoreboard players operation #err4 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #err4 fc_probe
