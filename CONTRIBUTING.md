# Contributing

The compiler is an experimental project. The research plan defines hypotheses,
proposed contracts, and gates; it does not establish that a hook, backend, or
optimization is correct or faster.

Use the [verification workflow](docs/verification.md) for the project loop,
test evidence, and Engineering Auditor conventions.

## Before changing runtime behavior

- Read the relevant architecture reference and the open questions in the
  research plan.
- Verify Minecraft-sensitive behavior against the exact target build. Keep
  nearby-version observations labeled as such.
- Preserve the original vanilla action as the fallback and cover quota,
  callback, trace, reload, and error behavior for any optimized path.
- Keep unsupported or mod-provided commands on vanilla execution.
- Record benchmark environment, workload, correctness evidence, distributions,
  and regressions alongside any performance claim.
- Follow the shared [benchmarking protocol](docs/benchmarking.md) for new
  optimization workloads, randomized paired timing, thresholds, and reports.

## Documentation and licensing

Update maintained reference pages when implementation or accepted decisions
change. Keep the proposed plan and its test matrix clearly labeled until their
claims are verified. Do not include decompiled Mojang source in commits. Review
the LGPL-3.0-or-later terms before copying or adapting code from MCFC.

## Build and verification

The pinned Minecraft 26.3 Fabric toolchain is documented in
[`docs/research/toolchain.lock`](docs/research/toolchain.lock). Build with Java
25 using `./gradlew build`. Run the wrapper and low-quota probe with
`python3 scripts/run_runtime_probe.py`; it creates temporary server worlds and
logs under ignored `run/` and `build/` directories. Use
`FC_GRADLE_OFFLINE=true` when the required Gradle and Minecraft artifacts are
already cached and network access is unavailable.

Run the small benchmark-analysis unit tests with
`python3 -m unittest discover -s tests -p 'test_*.py'`. For advisory static
review, run `bash scripts/run_ea_review.sh`; it verifies the pinned EA v1.5.0
worktree and does not act as a correctness or release gate. See
[`docs/verification.md`](docs/verification.md) for its limits.
