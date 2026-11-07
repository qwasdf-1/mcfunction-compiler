# Coverage row ST-02, second half: the bossbar set/get property shapes whose
# results vanilla defines as the written or read number. The add/remove
# lifecycle and the unknown-bar edge live in st02_bossbar_ops; this fixture is
# separate because the full property sweep does not fit one 0-16 quota sweep.
#
# 26.3 facts, read from the pinned vanilla server rather than assumed:
# `bossbar set <id> value|max <v>` returns the new number as the command
# result when the value changed and 0 with "Nothing changed. That's already
# the ..." when it did not. `bossbar get <id> players` returns the
# online-player count, 0 here. The leading bare remove resets the bar
# idempotently every run (a failing remove on an absent bar is an error that
# does not abort the remaining lines), so the fresh-bar defaults (value 0,
# max 100) make both set results deterministic changes in every iteration.
#
# Case 1 (+1) branches on the stored `set value 43` result 43. A skipped
# store leaves the re-add's result 1, so the branch is falsifiable.
#
# Case 2 (+2) branches on the stored `set max 200` result 200. A skipped
# store leaves 43.
#
# Case 3 (+4) stores the `bossbar get players` result 0. The previous store
# left 200, so the branch on 0 fires only if the store actually wrote the
# measured getter result. It is the final case and always fires on a complete
# run - the completion signal.
#
# expected 1,1,1 = 7
bossbar remove function_compiler_probe:st02
execute store result score #st02 fc_probe run bossbar add function_compiler_probe:st02 probe
execute store result score #st02 fc_probe run bossbar set function_compiler_probe:st02 value 43
execute if score #st02 fc_probe matches 43 run scoreboard players add #fcprobe fc_probe 1
execute store result score #st02 fc_probe run bossbar set function_compiler_probe:st02 max 200
execute if score #st02 fc_probe matches 200 run scoreboard players add #fcprobe fc_probe 2
execute store result score #st02 fc_probe run bossbar get function_compiler_probe:st02 players
execute if score #st02 fc_probe matches 0 run scoreboard players add #fcprobe fc_probe 4
