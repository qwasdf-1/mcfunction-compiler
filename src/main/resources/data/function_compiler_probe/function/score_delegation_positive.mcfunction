# Positive control for the delegation-contract measurement (batch 5).
#
# Every command here has a `#` fake-holder operand and a literal other side, so
# the specialized scoreboard path accepts all of them. This function exists so
# the measurement used to check the declined fixtures is accountable: if
# `score_add_compiled_lifecycle_probe` and these seeds were also zero, the
# counters would prove nothing.
#
# The specialization counters for the declined fixtures are exposed per function
# by `function_compiler_probe status`
# (`delegation_selector_compiled`, `delegation_client_packet_compiled`), so this
# control is checked indirectly: the same status command must report a nonzero
# count for an accepted function, and zero for the declined ones.
scoreboard players set #delegation_control fc_probe 3
scoreboard players add #delegation_control fc_probe 4
