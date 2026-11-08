# Second tick member of the same pack. It copies the accumulated tick count
# after the first tick function has run, which records the intra-tick member
# order without consuming or changing the count itself.
scoreboard players operation #tick_after fc_lifecycle = #tick fc_lifecycle
