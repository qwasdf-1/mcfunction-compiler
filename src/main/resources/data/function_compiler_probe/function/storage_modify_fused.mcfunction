data modify storage function_compiler_probe:temp state set value {count:10,flag:1}
scoreboard players set #store_test fc_probe 100
data modify storage function_compiler_probe:temp state.flag set value 2
scoreboard players add #store_test fc_probe 50
data remove storage function_compiler_probe:temp state.flag
scoreboard players add #store_test fc_probe 25
