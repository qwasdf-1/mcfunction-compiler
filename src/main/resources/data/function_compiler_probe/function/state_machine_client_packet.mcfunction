# Delegation contract for the client-packet-only command families (batch 5),
# covering rows ST-01 (`title`), ST-05 (`playsound`/`particle`/`stopsound`) and
# ST-07 (the generic state-machine wrapper around them).
#
# These families have no server-side observable effect: a title, a sound, a
# particle and a stop-sound all produce client packets only, and RCON cannot see
# any of them. No differential oracle exists for those effects, so these rows
# cannot be closed by a parity test and instead rest on an explicit delegation
# contract. The contract has two parts, and both are checked per arm:
#
# 1. Behavioural: this function loads and runs to completion in every arm with
#    no command error, which is what "delegated to vanilla" looks like from the
#    server side. The commands are recognized by the function parser, so a
#    mishandled command would abort the function load or fail at run time.
# 2. Structural: `delegation_client_packet_compiled` and
#    `delegation_client_packet_executed` on `function_compiler_probe status`
#    stay at zero, so no specialized engine claims any of these commands.
#
# What this contract does *not* claim: the text, sound volume/pitch, particle
# counts and channel semantics themselves. Those would need a packet-capturing
# client, which is a v1 decision recorded in the coverage table rather than
# something a server-side harness can settle.
#
# Coordinates are absolute rather than `~ ~ ~`: this function is invoked from
# the console, where a relative position would be resolved against a source
# with no block position.
title @a actionbar {"text":"fc","color":"yellow"}
playsound minecraft:block.note_block.pling master @a 0 100 0 1 1
particle minecraft:happy_villager 0 100 0 0 0 0 1 1
stopsound @a master
