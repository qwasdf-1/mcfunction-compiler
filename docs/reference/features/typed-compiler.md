# Opt-in typed compiler

The typed compiler targets Minecraft 26.3 Fabric, Java 25. It remains disabled by default and is a maintained experimental surface, not an unrestricted compiler. The legacy configuration remains documented in [configuration](../configuration.md).

## Enable for a selected namespace

```sh
FC_TYPED_COMPILER_PROFILE=validated FC_TYPED_IR_NAMESPACE=my_pack java -jar fabric-server-launch.jar nogui
```

Startup environment, restart required. A missing/blank namespace does not activate this profile. The profile defaults to bytecode and the existing wrapper gate; explicit legacy/typed environment overrides retain precedence, including explicit off. Namespace exclusions remain effective. Optional `FC_TYPED_IR_FUNCTION_FILTER` is an exact comma-separated list of IDs within the selected namespace. `FC_TYPED_IR_MODE=interpreted` selects the reference interpreter; `FC_TYPED_IR_DIAGNOSTICS=true` adds opt-in counters. Inspect `/functioncompiler status`, `/functioncompiler ir008` and `/functioncompiler ir016 <namespace:function>`. The status reports requested profile, mode, namespace and reentrant/reuse flags, not admission of each function.

## Pipeline and invariants

1. Vanilla constructs parsed commands; eligible plain-text functions are passed through the existing wrapper, native context and source-shape checks.
2. Ordered mixed IR holds bounded 2–64-command typed score regions and single native dispatch/guard/store boundaries. Unsupported and isolated typed source entries remain original native queue actions. Bytecode compilation failure falls back to the interpreted typed action.
3. Prepared steps and the canonical opcode plan are shared by interpreter and ASM. Runtime preserves native quota debits, tracing, feedback, callback and error paths, and queued work ordering. Unsupported assumptions fall back to the original action before effects where applicable.
4. Compound preflight and predicate facts are local to a command except the narrowly proven adjacent failed-guard run. IR046/047 reuse only identical ordered positive range/SET slots in one invocation after pure failure; invalidate before terminal effects and on barriers/fallback/yield. No persistent Objective, holder, mutable ScoreAccess or selector membership cache.

The profile enables range guards, self holder, extended score, compound score, dataflow, native arithmetic, reentrant-safe queue, dispatch, terminal guards, native store, guard-run value reuse and guard preflight reuse. Their individual FC_TYPED_IR flags remain available for controlled experiments. Direct scheduler and singleton-feedback options are not enabled by the profile. Do not combine with legacy parser prototypes without separately verifying the interaction. Macro typed compilation, general selector transformations and singleton specialization are not supported claims.

## Packaging and verification

Ordinary builds exclude synthetic commands and adversarial scoreboard observers. Explicit `./gradlew -PfcIntegrationFixtures=true build` selects a fixture-only source/resource set and suffixes version with -fixtures. Never distribute that JAR. The native and controlled CPU suites use fixtures; default-off and profile smoke use production. Historical exact source and results are indexed in [compiler research history](../../research/compiler-history.md); current integration disposition and remaining gates are in [Integration-001](../../integration-001.md). Scoped native/CPU evidence is not proof of arbitrary mod compatibility or a measured whole-datapack gain.
