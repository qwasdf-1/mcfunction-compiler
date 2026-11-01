# Datapack Lifecycle and Reload Semantics

**Status:** Verified across all 10 runtime modes.  
**Reference Target:** Minecraft 26.3 `ServerFunctionLibrary`, `PackRepository`  
**Test IDs:** [`RELOAD-001`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L50) through [`RELOAD-004`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L54), [`HOOK-006`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L16), [`HOOK-008`](../../v1/plans/minecraft-function-compiler-test-matrix-v0.1.csv#L18)

---

## 1. Datapack Tag & Lifecycle Execution

When datapacks are loaded or reloaded:
- **`#minecraft:load`:** Executes once on server startup and after every successful reload. Functions in `#load` run in dependency order.
- **`#minecraft:tick`:** Runs every server tick (50ms).
- **Tag Resolution:** Tag membership resolves to current compiled or wrapped function instances.

---

## 2. Multi-Generation Reload Transitions

The lifecycle test harness sweeps 25 sequential reload cycles with changing function bodies and alternating tag targets (`probe` vs `probe_v2`):
- Function identity and wrapper instances update cleanly.
- Intermediate scoreboard modifications and macro expansions observe the new generation immediately upon publication.
- Function removal followed by re-addition confirms that removed functions become unknown immediately and regain compilation state upon re-addition.

---

## 3. Whole-Resource Reload Failure Rollback

If a resource reload fails during preparation (e.g., due to an invalid JSON structure, corrupted datapack, or injected reload listener exception):
- Vanilla logs `Reload failed; keeping old data`.
- The `ServerFunctionLibrary` rejects the prepared resources and retains the previously published function library and tag sets.
- Injected failure tests confirm that all 10 modes retain identical baseline scores, direct function responses, and macro definitions.
- For emitted bytecode, staged compilation emitted 39,715 class bytes; post-GC, zero uncommitted classes were retained and Metaspace growth was bounded at +16 KiB.

---

## 4. Concurrent Out-of-Order Publication

In multi-request overlapping reload scenarios (HOOK-008):
- Request A is held during preparation while requests B, C, D, E, and F publish.
- Releasing A causes A to publish last, overwriting intermediate states.
- Verified across all nine Fabric modes against mod-free vanilla: intermediate markers 404, 505, 606, 707, 808 appear in sequence, and final marker 303 publishes last with exact `#load` count parity (advancing 10→16).

---

## 5. Live Configuration Hot-Reloading

In addition to datapack resource reloads, the compiler supports live configuration updates without restarting the server:
- **Command:** `/functioncompiler reload` triggers [`CompilerConfig.reload()`](../../../src/main/java/dev/functioncompiler/CompilerConfig.java).
- **Behavior:** Reads `config/function-compiler.json` from disk, atomically updating active optimization toggles (`fused_regions`, `selective_macros`, `tiered_bytecode`, `tiered_threshold`) and namespace exclusion sets.
- **Safety:** Ongoing function executions finish cleanly; newly dispatched or instantiated functions immediately observe updated compilation rules.
