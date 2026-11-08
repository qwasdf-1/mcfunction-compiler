# Second datapack in the world contributing to #minecraft:load. It records
# the value the first pack's load tag function had reached when this pack's
# load ran, proving both packs' load tags run exactly once per reload and
# recording their relative order without touching the shared count.
scoreboard players operation #partner_seen fc_lifecycle = #load fc_lifecycle
