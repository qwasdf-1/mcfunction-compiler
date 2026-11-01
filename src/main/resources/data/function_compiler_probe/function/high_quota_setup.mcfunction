scoreboard objectives add fc_probe dummy
scoreboard players set #quota_linear fc_probe 0
scoreboard players set #quota_loop fc_probe 0
scoreboard players set #quota_fork fc_probe 0
kill @e[tag=fc_high_quota_marker]
