# Coverage rows SC-03 (a score condition where one side's score is absent) and
# SC-05 (conditions across selector shapes under store/callback contexts). An
# absent score is treated as zero by `matches`, so the range test takes the
# branch and the comparison test does not; the count proves which way each
# went. The `as @e` condition exercises the selector shape.
scoreboard players set #ten fc_probe 10
scoreboard players set #weight fc_probe 1
scoreboard players reset #absent_cond fc_probe
execute if score #absent_cond fc_probe matches 0.. run scoreboard players add #fcprobe fc_probe 1
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute unless score #absent_cond fc_probe matches 1.. run scoreboard players add #fcprobe fc_probe 10
scoreboard players operation #weight fc_probe *= #ten fc_probe
execute as @e[tag=fc_cond_actor] if score #absent_cond fc_probe matches 0.. run scoreboard players add #fcprobe fc_probe 100
