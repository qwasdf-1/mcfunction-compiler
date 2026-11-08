# MO-09: identity semantics for sort=random. Vanilla resolves sort=random
# non-deterministically by design (24 direct trials over actors a, b, c
# covered all three candidate pairs uniformly, every trial exactly two
# distinct actors), so the harness asserts per-trial set semantics - exactly
# two distinct selected actors - plus a distinct-pair floor across trials,
# not an identity order. The same swap-chain read-back as the arbitrary
# fixture identifies which actors were selected in each trial.
execute positioned 32 100 0 as @e[type=minecraft:armor_stand,tag=fc_fork_order,sort=random,limit=2] run scoreboard players operation #fork_order_acc fc_fork_order >< @s fc_fork_order
