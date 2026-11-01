# Command Quota and Scheduler (`ExecutionContext`)

**Status:** Verified semantic baseline across all 10 runtime modes.  
**Reference Target:** Minecraft 26.3 official dedicated server  
**Owner Classes:** `net.minecraft.commands.execution.ExecutionContext`, `Frame`, `CommandQueue`  
**Test IDs:** [`QUOTA-000`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L32) through [`QUOTA-009`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L41), [`CTRL-001`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L42) through [`CTRL-008`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L50)

---

## 1. Vanilla 26.3 Scheduler Mechanics

In Minecraft 26.3, command execution uses a depth-bounded, queue-based scheduler:
1. `ExecutionContext.queue`: A deque of scheduled command actions.
2. `ExecutionContext.commandLimit`: Governed by the `maxCommandChainLength` game rule (default 65,536). Every executed command decrements the remaining quota.
3. `ExecutionContext.forkLimit`: Maximum number of entity contexts spawned by a forked `execute as @e` command (swept 1–12 in tests).
4. `Frame`: Encapsulates call depth, return value slots, failure flags, and callback references.

---

## 2. Quota & Limit Sweeps

The compiler harness rigorously validates low-quota stops and limit transitions:
- **Direct Quota Stops (0–16):** Tested across empty, single-entry, nested, and recursive function fixtures. At limit 0, zero commands execute; at limit 1, exactly 1 command executes and subsequent actions remain unexecuted.
- **Sequence Limit Boundary:** A four-target `execute` followed by a function command stops through limit 7 and executes at limit 8 across mod-free vanilla and all nine Fabric modes.
- **Dynamic Limit Changes:** Modifying `maxCommandChainLength` mid-function updates the active execution quota immediately without restarting or skipping commands.

---

## 3. Frame Discard & Return Semantics

When `return run function`, `return <value>`, or `return fail` executes:
- **Frame Return Slot:** The frame records the numeric return value or failure flag.
- **Pending Tail Discard:** Any remaining queue entries or fused command tails associated with that frame are discarded immediately.
- **Parent Continuation:** The parent frame receives the result (e.g. via `execute store result` or `execute if function`) and continues execution at its next scheduled action.
- **Error Inversion:** In `execute unless function`, a child returning failure evaluates as false, taking the inverted branch with full parity.

All 88 command-level debug traces match mod-free vanilla byte-for-byte across all 10 modes.

---

## 4. Custom Mod Control Flow Interoperability (`CTRL-008`)

Modded commands implementing `CustomCommandExecutor` receive direct access to `ExecutionControl` and `Frame`:
- **Conservative Queue Fallback:** Custom mod commands are unrecognized by the region compiler and remain uncompiled `BuildContexts.Unbound` queue actions.
- **Single Invocation Guarantee:** Both continuing (`step`) and frame-terminating (`discard`, `returnSuccess`, `returnFailure`) mod commands execute exactly once without duplicate evaluation.
- **Region Boundaries:** Preceding fused/bytecode regions execute completely prior to the mod command; trailing regions execute if the frame continues, or are immediately purged from the scheduler if the frame discards or returns.
