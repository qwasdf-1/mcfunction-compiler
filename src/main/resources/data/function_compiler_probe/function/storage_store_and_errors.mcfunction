# Coverage rows DS-04 (data get on a malformed/absent path) and DS-05
# (execute store result/success around a data command). A successful read
# establishes a nonzero checksum first; the failing reads then must record
# success 0. Batch 8 measured the failing-read semantics directly (see the
# mo02_store_failures fixture): vanilla reports (success=false, result=0) to
# the store callback, so a result store writes 0 as well as a success store,
# overwriting the previous value. This fixture's later absent-path cases are
# therefore not observably taken inside the 0-16 sweep - the fold adds 0
# whether the store wrote 0 or skipped the write - which is why the
# falsifiable form of that claim lives in mo02_store_failures (exact 0L/0s
# tag matches). Run under the extended quota sweep (0-16).
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
