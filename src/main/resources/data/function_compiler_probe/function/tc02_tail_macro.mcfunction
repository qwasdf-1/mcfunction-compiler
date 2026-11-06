# Coverage row TC-02: a tail call through a macro invocation.
#
# The row is the cross-product of two mechanisms that the other rows test
# separately: the tail-call run (TC-01) and the macro argument family (MA-*).
# This fixture makes the final command of each frame a function call, and makes
# the first two of those calls macro invocations, so the chain is:
#
#   plain function -> macro function A -> macro function B -> plain leaf
#
# Every call is in tail position: nothing follows it in its own function. The
# leaf's final add is what proves the whole chain ran; the +1 and the two macro
# arguments prove that each frame contributed exactly once. A tail-call path
# that re-entered a frame, dropped the macro argument, or treated a `with`
# invocation as a plain call would change the total.
#
# The storage compound is written before every run, so the fixture does not
# depend on a previous quota iteration having reached the setup line. The same
# values are written each time, which keeps a truncated sweep harmless.
data modify storage function_compiler_probe:tc02 args set value {step:10,bonus:20}
scoreboard players add #fcprobe fc_probe 1
function function_compiler_probe:tc02_macro_a with storage function_compiler_probe:tc02 args
