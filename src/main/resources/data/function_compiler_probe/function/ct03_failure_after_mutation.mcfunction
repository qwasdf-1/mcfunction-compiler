# Coverage row CT-03: callback failures after a partial mutation do not replay
# the completed effects.
#
# Case 1 mutates +1 in the parent, then calls a macro function that mutates +10
# and then fails on a missing objective before mutating +20 again. The +1 and
# +10 are completed effects; a replay on the failure would add them twice. The
# parent's +100 proves the failure did not abort the caller.
#
# Case 2 mutates +1000, then invokes a macro function whose argument compound is
# missing a declared key. The expansion fails before any line of that function
# runs, so it contributes nothing; the +1000 is not replayed and the parent's
# +10000 still runs. The two cases use different failure sites - a runtime
# command error inside the callee and an expansion error at the call - because
# the row is about failure shapes other than the already-covered missing-
# objective score add.
data modify storage function_compiler_probe:ct03 args set value {step:10}
scoreboard players add #fcprobe fc_probe 1
function function_compiler_probe:ct03_macro_runtime_fail with storage function_compiler_probe:ct03 args
scoreboard players add #fcprobe fc_probe 100
scoreboard players add #fcprobe fc_probe 1000
function function_compiler_probe:ct03_macro_missing with storage function_compiler_probe:ct03 args
scoreboard players add #fcprobe fc_probe 10000
