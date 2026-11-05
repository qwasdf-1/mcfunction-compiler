# Delegation contract for the selector-shaped scoreboard rows (batch 5).
#
# Every command below has an entity-selector operand, or an entity-selector
# source, so the specialized scoreboard path must decline each one: the
# compiler resolves a static holder only when the operand text begins with `#`,
# and declines every other operand. The falsifiable form of that claim is the
# per-function specialization counter exposed by
# `function_compiler_probe status` (`delegation_selector_compiled` and
# `delegation_selector_executed`): both must stay at zero. If a future change
# makes any of these shapes specializable, the counter stops being zero and the
# contract stops holding, which is the point - the specialization would then
# need its own semantic gate before the fallback claim could be relied on.
#
# This fixture deliberately carries no score oracle of its own. Its job is the
# structural claim, and the behavioural claim for the same shapes lives in
# `score_selector_mutation`, `score_selector_store`, `score_selector_operation`
# and `score_modifier_dispatch`, which fold their per-entity effects into a
# score and compare across arms. Mixing the two in one fixture would make the
# counter ambiguous, because the fold's own command has a `@s` source that the
# compiler does accept.
#
# `score_delegation_positive` is the control for the measurement: the same
# status command must report nonzero counters for that function's fake-holder
# commands, otherwise a zero reading here would prove nothing.
scoreboard players set @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 10
scoreboard players add @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe 5
scoreboard players remove @e[type=minecraft:armor_stand,tag=fc_probe_actor,limit=2] fc_probe 3
scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe += @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
scoreboard players operation @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe = @e[type=minecraft:armor_stand,tag=fc_probe_actor] fc_probe
