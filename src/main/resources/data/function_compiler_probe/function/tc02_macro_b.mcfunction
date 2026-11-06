# TC-02 helper: the second macro frame. Its final command is a plain tail call,
# so the chain crosses back out of the macro path into an ordinary leaf.
$scoreboard players add #fcprobe fc_probe $(bonus)
function function_compiler_probe:tc02_leaf
