# MO-09: identity ordering for the unordered fork sorts. Measured on the
# pinned vanilla 26.3 server (batch 11): sort=arbitrary resolves candidates in
# entity insertion (summon) order - actors a, b, c here - and that order is
# stable across repeated invocations, /reload, a server restart on the same
# world, and fresh worlds with different seeds. The swap chain makes the
# selection order observable: with the accumulator at 100 and actor values
# a=2, b=3, c=5, the first forked actor ends at 100, the accumulator ends at
# the second actor's original value, and the second actor ends at the first
# actor's original value.
execute positioned 32 100 0 as @e[type=minecraft:armor_stand,tag=fc_fork_order,sort=arbitrary,limit=2] run scoreboard players operation #fork_order_acc fc_fork_order >< @s fc_fork_order
