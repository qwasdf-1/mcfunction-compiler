scoreboard players set #res_fail_store fc_probe 999
execute store result score #res_fail_store fc_probe run function function_compiler_probe:redteam_child_fail
scoreboard players add #res_fail_store fc_probe 5
