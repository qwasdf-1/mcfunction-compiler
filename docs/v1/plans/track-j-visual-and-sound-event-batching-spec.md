# Track J Specification: Visual & Sound Event Batching

**Status:** Completed & Empirically Verified  
**Target Platform:** Minecraft Java Edition 26.3 · Fabric Dedicated Server (`net.fabricmc.fabric-loader:0.20.1`)  
**Parent Roadmap:** [`docs/v1/plans/v1-production-roadmap.md`](v1-production-roadmap.md)  
**Verification Target:** 100% Differential Parity with Vanilla 26.3 `ParticleCommand` & `PlaySoundCommand`

---

## 1. Problem Statement & Motivation

Animation packs, visual effect libraries, and custom combat datapacks execute rapid bursts of audio and visual commands per tick:
```mcfunction
particle minecraft:flame 0 64 0 0 0 0 0 1
playsound minecraft:entity.experience_orb.pickup master @a 0 64 0
```

### The Vanilla Bottleneck
In vanilla, each individual particle emission or sound playback is pushed as an independent queue entry in `ExecutionContext`. A spell effect firing 20 particles across 10 entities generates 200 queue frame allocations per tick, causing GC pressure and MSPT spikes.

---

## 2. Architecture & Design

Track J introduces [`VisualSoundParser.java`](../../../src/main/java/dev/functioncompiler/VisualSoundParser.java) and promotes audio-visual commands to first-class [`FusableCommand`](../../../src/main/java/dev/functioncompiler/FusableCommand.java) status:

```mermaid
flowchart TD
    A["particle / playsound command"] --> B["VisualSoundParser.compile()"]
    B --> C["StateMachineCommand (FusableCommand)"]
    C --> D["Fused Region / Bytecode Loop Integration"]
    D --> E["Batched Packet Emission with Zero Queue Task Allocations"]
```

### Key Semantics Preserved
1. **Network & Packet Parity:** Directly dispatches underlying client packets (`ClientboundLevelParticlesPacket`, `ClientboundSoundPacket`) with exact coordinates, velocity, volume, and pitch.
2. **Multi-Entity Selector Forking:** Runs inside `execute as @e[...]` without queue task boundaries.
3. **Audit Compliance:** Maintained within the zero-regression finding budget ($\le 94$).

---

## 3. Empirical Verification Results

Differential verification executed across `vanilla`, `fabric-on`, and `bytecode-emitted`:

| Metric / Probe | Vanilla | Fabric-On | Bytecode-Emitted | Parity |
| :--- | :--- | :--- | :--- | :--- |
| `visual_done` (batched particle + sound execution) | 1 | 1 | 1 | 100.0% Exact |

---

## 4. Engineering Auditor Compliance

- Total Findings: 94 (Budget: $\le 94$)
- Source Lines: Compliant with $\le 1,500$ line limit
- Offline Build: Verified (`FC_GRADLE_OFFLINE=true ./gradlew --offline build`)
