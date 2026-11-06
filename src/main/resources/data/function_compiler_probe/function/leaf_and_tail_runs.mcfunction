# Coverage rows LF-01 (two or more contiguous plain-function leaf calls) and
# TC-01 (a tail-call run whose final command is another function call).
# The two leaf calls are contiguous, so a leaf parser that groups them can
# fuse the pair; the tail-call chain then walks one further level.
function function_compiler_probe:leaf_score_a
function function_compiler_probe:leaf_score_b
scoreboard players operation #fcprobe fc_probe = #leaf_marks fc_probe
scoreboard players operation #weight fc_probe *= #ten fc_probe
function function_compiler_probe:leaf_tail_a
scoreboard players operation #fcprobe fc_probe += #leaf_marks fc_probe
