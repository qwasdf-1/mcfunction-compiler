# Coverage rows SM-03 (a literal player-name holder that is neither a fake
# `#` holder nor `@s`) and SM-11 (INT_MIN/INT_MAX overflow edges). The literal
# holder is read back through scoreboard operation; the overflow chain adds
# INT_MAX and then INT_MAX + 1, which must wrap to INT_MIN.
scoreboard players set FCFused fc_probe 4
scoreboard players operation #fcprobe fc_probe = FCFused fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
scoreboard players set #ov fc_probe 2147483647
scoreboard players operation #fcprobe fc_probe += #ov fc_probe
scoreboard players add #ov fc_probe 1
scoreboard players operation #fcprobe fc_probe += #ov fc_probe
scoreboard players remove #ov fc_probe 1
scoreboard players operation #fcprobe fc_probe += #ov fc_probe
