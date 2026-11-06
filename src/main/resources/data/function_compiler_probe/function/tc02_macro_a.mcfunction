# TC-02 helper: the first macro frame. Its final command is another macro
# invocation in tail position, so the frame must be able to hand off without
# leaving a pending continuation behind.
$scoreboard players add #fcprobe fc_probe $(step)
function function_compiler_probe:tc02_macro_b with storage function_compiler_probe:tc02 args
