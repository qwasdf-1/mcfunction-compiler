# Multi-level storage modifications
data modify storage redteam:ferrite root.a.b.c set value {k1: 100, k2: "test"}
data modify storage redteam:ferrite root.a.b.c.k1 set value 200
data modify storage redteam:ferrite root.a.b.d set value [10, 20, 30]
data remove storage redteam:ferrite root.a.b.c.k2
execute store result score #ferrite_k1 fc_probe run data get storage redteam:ferrite root.a.b.c.k1
execute store result score #ferrite_len fc_probe run data get storage redteam:ferrite root.a.b.d
