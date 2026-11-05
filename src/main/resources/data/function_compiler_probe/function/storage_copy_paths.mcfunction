# Coverage rows DC-01 (storage-to-storage copy) and DC-02 (nested path and
# array-index copy). Reads the copied values back through the weighted
# checksum, including a read of the copied list itself so a wrongly copied
# container is observable. Run under the extended quota sweep (0-16).
scoreboard players set #ten fc_probe 10
scoreboard players set #weight fc_probe 1
data modify storage function_compiler_probe:covcopy source set value {deep:{inner:[11,22,33]},scalar:9}
data modify storage function_compiler_probe:covcopy target set from storage function_compiler_probe:covcopy source.deep
execute store result score #copy1 fc_probe run data get storage function_compiler_probe:covcopy target.inner[2]
scoreboard players operation #fcprobe fc_probe = #copy1 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
data modify storage function_compiler_probe:covcopy target2 set from storage function_compiler_probe:covcopy source.deep.inner[0]
execute store result score #copy2 fc_probe run data get storage function_compiler_probe:covcopy target2
scoreboard players operation #copy2 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #copy2 fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
data remove storage function_compiler_probe:covcopy source.deep.inner[1]
execute store result score #copy3 fc_probe run data get storage function_compiler_probe:covcopy target.inner
scoreboard players operation #copy3 fc_probe *= #weight fc_probe
scoreboard players operation #fcprobe fc_probe += #copy3 fc_probe
