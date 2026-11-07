# Coverage row ST-02, first half: the bossbar command family through the
# StateMachineCommand wrap (BossbarParser wraps every command whose class
# nest-host is BossBarCommands). The set-shape results and the players getter
# live in st02_bossbar_values; this fixture holds the add/remove lifecycle and
# the row's unknown-bar edge. Both halves are separate because a full
# lifecycle does not fit one 0-16 quota sweep.
#
# 26.3 facts, read from the pinned vanilla server rather than assumed:
# `bossbar add` returns result 1 on success and fails with "A bossbar already
# exists with the ID ..." on a duplicate; `bossbar get <id> value` returns the
# value as the command result; `bossbar remove` returns result 0 whether or
# not a bar was removed, and a get on an absent bar fails with "No bossbar
# exists with the ID '<id>'". A bare failing bossbar command does not abort
# the remaining function lines - the leading bare remove exploits that to
# reset the bar idempotently at a cost of one quota debit. A store-wrapped
# failing get reports (success=false, result=0) to the store callback, so the
# store writes 0. Bare `bossbar get <id>` (no property) is not a valid 26.3
# form - the only getters are value, max and players.
#
# Every case is a taken branch, so a truncated tail lowers the total instead
# of looking like an executed case:
#
# Case 1 (+1) removes any leftover bar bare (a failing remove on an absent
# bar is an error that does not abort) and branches on the stored `bossbar
# add` result 1. A skipped store leaves the remove's 0, so the branch is
# falsifiable.
#
# Case 2 (+2) sets value 43 on the fresh bar and branches on the stored
# `bossbar get value` result 43.
#
# Case 3 (+4) removes the bar bare and stores the `bossbar get value` of the
# now-absent bar. The previous read left 43, so the branch on 0 fires only if
# the failing store actually wrote vanilla's measured failure value. It is the
# final case and always fires on a complete run - the completion signal.
#
# expected 1,1,1 = 7
bossbar remove function_compiler_probe:st02
execute store result score #st02 fc_probe run bossbar add function_compiler_probe:st02 probe
execute if score #st02 fc_probe matches 1 run scoreboard players add #fcprobe fc_probe 1
bossbar set function_compiler_probe:st02 value 43
execute store result score #st02 fc_probe run bossbar get function_compiler_probe:st02 value
execute if score #st02 fc_probe matches 43 run scoreboard players add #fcprobe fc_probe 2
bossbar remove function_compiler_probe:st02
execute store result score #st02 fc_probe run bossbar get function_compiler_probe:st02 value
execute if score #st02 fc_probe matches 0 run scoreboard players add #fcprobe fc_probe 4
