forceload add 0 0 32 32
kill @e[tag=fc_track_a]
scoreboard objectives add fc_probe dummy
summon armor_stand 10.0 64.0 10.0 {Tags:["fc_track_a","fc_spatial_a"]}
summon armor_stand 20.0 70.0 20.0 {Tags:["fc_track_a","fc_spatial_a"]}
summon armor_stand 30.0 80.0 30.0 {Tags:["fc_track_a","fc_spatial_a"]}
summon pig 0.0 64.0 0.0 {Tags:["fc_track_a","fc_mount"],Passengers:[{id:"armor_stand",Tags:["fc_track_a","fc_rider"]}]}
