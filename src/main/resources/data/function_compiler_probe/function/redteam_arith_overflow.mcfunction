# Test integer overflow wrapping vs exception
scoreboard players set #res_add_overflow fc_probe 0
scoreboard players set #res_remove_underflow fc_probe 0
scoreboard players set #res_mul_overflow fc_probe 0
scoreboard players set #res_sub_underflow fc_probe 0

# Integer.MAX_VALUE + 1 -> Integer.MIN_VALUE (-2147483648)
scoreboard players set #target_add fc_probe 2147483647
scoreboard players add #target_add fc_probe 1
scoreboard players operation #res_add_overflow fc_probe = #target_add fc_probe

# Integer.MIN_VALUE - 1 -> Integer.MAX_VALUE (2147483647)
scoreboard players set #target_rem fc_probe -2147483648
scoreboard players remove #target_rem fc_probe 1
scoreboard players operation #res_remove_underflow fc_probe = #target_rem fc_probe

# Integer.MAX_VALUE * 2 -> -2
scoreboard players set #target_mul fc_probe 2147483647
scoreboard players set #mul_two fc_probe 2
scoreboard players operation #target_mul fc_probe *= #mul_two fc_probe
scoreboard players operation #res_mul_overflow fc_probe = #target_mul fc_probe

# Integer.MIN_VALUE - 1 via operation -= -> 2147483647
scoreboard players set #target_sub fc_probe -2147483648
scoreboard players set #sub_one fc_probe 1
scoreboard players operation #target_sub fc_probe -= #sub_one fc_probe
scoreboard players operation #res_sub_underflow fc_probe = #target_sub fc_probe
