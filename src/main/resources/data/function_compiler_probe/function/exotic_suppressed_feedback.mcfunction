scoreboard players add #feedback_target fc_probe 10
scoreboard players set #feedback_target fc_probe 20
scoreboard players remove #feedback_target fc_probe 5
data modify storage redteam:fb_storage val set value 42
return 99
