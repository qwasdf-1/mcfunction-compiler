#!/usr/bin/env python3
"""Run paired randomized compiler-off/candidate Vein Miner profiles."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import random
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "mc-tooling" / "mc-harness"))
from mc_harness import assert_version  # noqa: E402
from mc_harness.paired_stats import (  # noqa: E402
    paired_percent_changes,
    summarize_paired_changes,
)

#: The harness version this campaign was verified against (roadmap step 6 pin).
HARNESS_PIN = "1.0.0"

assert_version(HARNESS_PIN)
PROFILE_RUNNER = ROOT / "scripts/run_veinminer_profile.py"
CAMPAIGN_ROOT = ROOT / "build/benchmarks/PERF-011-veinminer/campaigns"

PARITY_FIELDS = (
    "player_mined_source_stat",
    "work_after",
    "work_expected",
    "run_state_after",
    "queue_head_delta",
    "remaining_ore",
    "source_block_remains",
    "operation_markers_after",
    "target_markers_after",
)


def tick_metrics(query: str) -> dict[str, float | None]:
    patterns = {
        "tick_average_ms": r"Average time per tick: ([0-9.]+)ms",
        "tick_p50_ms": r"P50: ([0-9.]+)ms",
        "tick_p95_ms": r"P95: ([0-9.]+)ms",
        "tick_p99_ms": r"P99: ([0-9.]+)ms",
    }
    values: dict[str, float | None] = {}
    for name, pattern in patterns.items():
        match = re.search(pattern, query)
        values[name] = float(match.group(1)) if match else None
    return values


def profile_command(
    args: argparse.Namespace,
    mode: str,
    *,
    count_selective_macro_arguments: bool = False,
) -> list[str]:
    """Build one profile-runner command.

    Paired timing arms are symmetric and uninstrumented: the fused candidate
    runs the profile runner's ``fused-timed`` mode, and the selective-macro
    candidate runs plain ``selective-macro``. A mechanism's fast path is
    proven by a separate metrics-on activation diagnostic, never by a timing
    arm; the selective-macro hit counter in particular perturbs timing.
    """
    profile_mode = "fused-timed" if mode == "fused" else mode
    command = [
        sys.executable,
        str(PROFILE_RUNNER),
        "--stack",
        args.stack,
        "--compiler-mode",
        profile_mode,
        "--side",
        str(args.side),
        "--capture-timeout",
        str(args.capture_timeout),
        "--no-spark",
    ]
    if count_selective_macro_arguments:
        if mode != "selective-macro":
            raise ValueError(
                "the selective-macro hit counter is only valid on the "
                f"selective-macro activation diagnostic, not {mode!r}"
            )
        command.append("--count-selective-macro-arguments")
    return command


def selective_activation_summary(
    profile: dict[str, object],
    result: dict[str, object],
) -> dict[str, object]:
    """Validate a metrics-on selective-macro run and summarize its activation.

    The run is a diagnostic, not a timing arm. It must pass the native
    workload gate, pass the selective-macro profile gate, and show that the
    fast path handled real macro calls.
    """
    if not result.get("valid_native_workload"):
        raise ValueError("activation diagnostic failed the native workload gate")
    if not result.get("valid_selective_macro_profile"):
        raise ValueError(
            "activation diagnostic failed the selective-macro profile gate"
        )
    calls = result.get("selective_macro_argument_calls_delta")
    if not isinstance(calls, int) or calls <= 0:
        raise ValueError(
            f"activation diagnostic intercepted no macro calls: {calls!r}"
        )
    diagnostics = result.get("selective_macro_diagnostics_delta") or {}
    attempted = int(diagnostics.get("attempted") or 0)
    if attempted <= 0:
        raise ValueError(
            f"activation diagnostic attempted no macro calls: {diagnostics!r}"
        )
    return {
        "run_id": Path(str(profile.get("output"))).name,
        "valid_native_workload": result["valid_native_workload"],
        "valid_selective_macro_profile": result["valid_selective_macro_profile"],
        "selective_macro_arguments_metrics_enabled": result.get(
            "selective_macro_arguments_metrics_enabled"
        ),
        "selective_macro_argument_calls_delta": calls,
        "selective_macro_diagnostics_delta": diagnostics,
        "selective_macro_provider_class_delta": result.get(
            "selective_macro_provider_class_delta"
        ),
        "work_after": result.get("work_after"),
        "work_expected": result.get("work_expected"),
        "queue_head_delta": result.get("queue_head_delta"),
        "operation_completion_seconds": result.get("operation_completion_seconds"),
        "timing_instrumentation": result.get("timing_instrumentation"),
        "valid_activation": True,
    }


def run_selective_activation_diagnostic(
    args: argparse.Namespace,
    report: dict[str, object],
    report_path: Path,
) -> dict[str, object]:
    """Run or retain the one-time metrics-on selective-macro diagnostic."""
    existing = report.get("activation_diagnostic")
    if isinstance(existing, dict) and existing.get("valid_activation"):
        print(
            "retaining completed selective-macro activation diagnostic",
            flush=True,
        )
        return existing
    print(
        "starting selective-macro activation diagnostic "
        f"(metrics on; not a timing arm) side={args.side}",
        flush=True,
    )
    command = profile_command(
        args, "selective-macro", count_selective_macro_arguments=True
    )
    completed = subprocess.run(
        command,
        cwd=ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        report["status"] = "failed"
        report["failure"] = {
            "phase": "activation-diagnostic",
            "returncode": completed.returncode,
            "stdout_tail": completed.stdout[-3000:],
            "stderr_tail": completed.stderr[-3000:],
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(
            f"Selective-macro activation diagnostic failed; report: {report_path}"
        )
    try:
        profile = json.loads(completed.stdout)
    except json.JSONDecodeError as error:
        report["status"] = "failed"
        report["failure"] = {
            "phase": "activation-diagnostic",
            "stdout_tail": completed.stdout[-3000:],
            "stderr_tail": completed.stderr[-3000:],
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(
            f"Selective-macro activation diagnostic emitted invalid JSON: {error}"
        ) from error
    try:
        activation = selective_activation_summary(profile, profile["results"])
    except ValueError as error:
        report["status"] = "failed"
        report["failure"] = {
            "phase": "activation-diagnostic",
            "error": str(error),
            "stdout_tail": completed.stdout[-3000:],
            "stderr_tail": completed.stderr[-3000:],
        }
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        raise RuntimeError(
            f"Selective-macro activation diagnostic gate failed: {error}"
        ) from error
    report["activation_diagnostic"] = activation
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(
        "activation diagnostic passed; "
        f"calls={activation['selective_macro_argument_calls_delta']} "
        f"work={activation['work_after']}/{activation['work_expected']}",
        flush=True,
    )
    return activation


def profile_summary(
    profile: dict[str, object],
    result: dict[str, object],
) -> dict[str, object]:
    summary: dict[str, object] = {
        "run_id": Path(str(profile["output"])).name,
        "stack": result["stack"],
        "compiler_mode": result["compiler_mode"],
        "valid_native_workload": result["valid_native_workload"],
        "valid_score_add_profile": result["valid_score_add_profile"],
        "valid_selective_macro_profile": result["valid_selective_macro_profile"],
        "valid_fused_timed_profile": result.get("valid_fused_timed_profile"),
        "fused_regions_compiled": result.get("fused_regions_compiled"),
        "fused_regions_executed_delta": result.get("fused_regions_executed_delta"),
        "score_add_executed_delta": result.get("score_add_executed_delta"),
        "selective_macro_argument_calls_delta": result[
            "selective_macro_argument_calls_delta"
        ],
        "selective_macro_diagnostics_delta": result.get(
            "selective_macro_diagnostics_delta"
        ),
        "selective_macro_provider_class_delta": result.get(
            "selective_macro_provider_class_delta"
        ),        "work_after": result["work_after"],
        "work_expected": result["work_expected"],
        "queue_head_delta": result["queue_head_delta"],
        "queue_score_add_compiled": result["queue_score_add_compiled"],
        "remaining_ore": result["remaining_ore"],
        "operation_completion_seconds": result["operation_completion_seconds"],
        "spark_capture_seconds": result["spark_capture_seconds"],
        "spark_thread_nodes": result["spark_thread_nodes"],
        "server_function_manager_execute_weighted_ms": result[
            "server_function_manager_execute_weighted_ms"
        ],
        "profile_path": result["profile_path"],
        "profile_sha256": result["profile_sha256"],
    }
    summary.update(tick_metrics(str(result["tick_query_after_capture"])))
    summary["parity_state"] = {
        field: result[field]
        for field in PARITY_FIELDS
    }
    return summary


def make_report(args: argparse.Namespace) -> dict[str, object]:
    if args.resume_report:
        report_path = Path(args.resume_report)
        if not report_path.is_absolute():
            report_path = ROOT / report_path
        report_path = report_path.resolve()
        report = json.loads(report_path.read_text(encoding="utf-8"))
        expected = {
            "benchmark": "PERF-011",
            "datapack": "Vein Miner 5.3.0 (26.3)",
            "stack": args.stack,
            "cube_side": args.side,
            "pairs_requested": args.pairs,
            "random_seed": args.seed,
            "capture_timeout_seconds": args.capture_timeout,
            "analysis_plan": {
                "phase": args.phase,
                "primary_metric": args.primary_metric,
                "minimum_gain_percent": args.minimum_gain_percent,
                "planned_pairs": args.pairs,
                "confidence": 0.95,
                "ci_method": "exact sign/order-statistic interval for median paired percent change",
            },
        }
        mismatches = {
            key: (report.get(key), value)
            for key, value in expected.items()
            if report.get(key) != value
        }
        if mismatches:
            raise ValueError(f"Resume options do not match campaign: {mismatches}")
        existing_candidate = report.get("candidate", "score-add")
        if existing_candidate != args.candidate:
            raise ValueError(
                f"Resume candidate mismatch: {existing_candidate!r} != {args.candidate!r}"
            )
        report["candidate"] = args.candidate
        if report.get("status") != "running":
            raise ValueError(
                f"Only an interrupted running campaign can be resumed; status={report.get('status')!r}"
            )
        if len(report.get("pairs", [])) != len(report.get("pair_orders", [])):
            raise ValueError("Campaign pair and randomized-order records do not match")
        report["report_path"] = str(report_path.relative_to(ROOT))
        report["pairs"].sort(key=lambda pair: int(pair["repetition"]))
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        report_path = CAMPAIGN_ROOT / (
            f"vein-{args.side}-{args.stack}-{args.candidate}-"
            f"{args.pairs}pairs-seed{args.seed}-{timestamp}.json"
        )
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "benchmark": "PERF-011",
            "datapack": "Vein Miner 5.3.0 (26.3)",
            "stack": args.stack,
            "candidate": args.candidate,
            "cube_side": args.side,
            "blocks_in_vein": args.side**3,
            "pairs_requested": args.pairs,
            "random_seed": args.seed,
            "capture_timeout_seconds": args.capture_timeout,
            "analysis_plan": {
                "phase": args.phase,
                "primary_metric": args.primary_metric,
                "minimum_gain_percent": args.minimum_gain_percent,
                "planned_pairs": args.pairs,
                "confidence": 0.95,
                "ci_method": "exact sign/order-statistic interval for median paired percent change",
            },
            "pair_orders": [],
            "pairs": [],
            "report_path": str(report_path.relative_to(ROOT)),
            "status": "running",
        }

    if args.candidate == "selective-macro":
        run_selective_activation_diagnostic(args, report, report_path)

    rng = random.Random(args.seed)
    pairs: list[dict[str, object]] = report["pairs"]
    orders: list[list[str]] = report["pair_orders"]
    for repetition in range(1, args.pairs + 1):
        modes = ["off", args.candidate]
        rng.shuffle(modes)
        if repetition <= len(orders):
            if orders[repetition - 1] != modes:
                raise ValueError(f"Seeded order mismatch for pair {repetition}")
        else:
            orders.append(modes.copy())
        if repetition <= len(pairs):
            pair = pairs[repetition - 1]
            if pair.get("repetition") != repetition or pair.get("order") != modes:
                raise ValueError(f"Existing pair {repetition} does not match its seeded order")
            arms = pair["arms"]
        else:
            arms = {}
            pair = {"repetition": repetition, "order": modes, "arms": arms}
            pairs.append(pair)
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

        for mode in modes:
            if mode in arms:
                print(
                    f"pair {repetition}/{args.pairs}: retaining completed {args.stack} {mode} arm",
                    flush=True,
                )
                continue
            print(
                f"pair {repetition}/{args.pairs}: starting {args.stack} {mode} side={args.side}",
                flush=True,
            )
            # Both timing arms are uninstrumented. The fused candidate runs the
            # profile runner's `fused-timed` mode, and the selective-macro
            # candidate runs plain `selective-macro`; each mechanism's fast path
            # is proven separately by a metrics-on activation diagnostic.
            command = profile_command(args, mode)
            environment = os.environ.copy()
            completed = subprocess.run(
                command,
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
            )
            if completed.returncode != 0:
                report["status"] = "failed"
                report["failure"] = {
                    "pair": repetition,
                    "mode": mode,
                    "returncode": completed.returncode,
                    "stdout_tail": completed.stdout[-3000:],
                    "stderr_tail": completed.stderr[-3000:],
                }
                report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                raise RuntimeError(
                    f"Profile failed ({mode}, pair {repetition}); report: {report_path}"
                )
            try:
                profile = json.loads(completed.stdout)
            except json.JSONDecodeError as error:
                report["status"] = "failed"
                report["failure"] = {
                    "pair": repetition,
                    "mode": mode,
                    "stdout_tail": completed.stdout[-3000:],
                    "stderr_tail": completed.stderr[-3000:],
                }
                report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
                raise RuntimeError(f"Profile emitted invalid JSON: {error}") from error
            result = profile["results"]
            if not result["valid_native_workload"]:
                raise RuntimeError(f"Native workload gate failed in {mode}: {result}")
            if mode == "fused" and not result["valid_fused_timed_profile"]:
                raise RuntimeError(f"Fused candidate arm gate failed: {result['run_id']}")
            if mode == "score-add" and not result["valid_score_add_profile"]:
                raise RuntimeError(f"ScoreAdd compile gate failed: {result}")
            if mode == "selective-macro" and not result["valid_selective_macro_profile"]:
                raise RuntimeError(f"Selective macro activation gate failed: {result}")
            arms[mode] = profile_summary(profile, result)
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            print(
                f"pair {repetition}/{args.pairs}: {mode} passed; "
                f"work={result['work_after']}/{result['work_expected']} "
                f"head={result['queue_head_delta']} "
                f"completion={result['operation_completion_seconds']:.3f}s",
                flush=True,
            )

        off_result = next(
            result for result in arms.values() if result["compiler_mode"] == "off"
        )
        # The fused candidate runs the profile runner's symmetric "fused-timed"
        # mode, so the arm's recorded compiler_mode is the profile mode, not the
        # campaign candidate name.
        candidate_profile_mode = "fused-timed" if args.candidate == "fused" else args.candidate
        candidate_result = next(
            result
            for result in arms.values()
            if result["compiler_mode"] == candidate_profile_mode
        )
        pair["off"] = off_result
        pair[args.candidate] = candidate_result
        pair["candidate_mode"] = args.candidate
        pair["exact_parity"] = (
            off_result["parity_state"] == candidate_result["parity_state"]
        )
        report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        if not pair["exact_parity"]:
            report["status"] = "failed"
            report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
            raise RuntimeError(f"Off/on workload state diverged in pair {repetition}")

    diagnostic_keys = (
        "attempted",
        "unsupported_providers",
        "unsupported_entity_paths",
        "invalid_storage_sources",
        "missing_entity_custom_data",
        "macro_resolution_fallbacks",
        "missing_selected_keys",
    )
    activation = report.get("activation_diagnostic")
    if isinstance(activation, dict):
        # The paired timing arms are uninstrumented, so the campaign's
        # selective-macro counters come from the one-time activation
        # diagnostic rather than from summing per-pair (absent) deltas.
        diagnostics = activation.get("selective_macro_diagnostics_delta") or {}
        report["selective_macro_diagnostics_total"] = {
            key: int(diagnostics.get(key, 0) or 0) for key in diagnostic_keys
        }
        report["selective_macro_provider_class_total"] = {
            str(provider): int(count)
            for provider, count in (
                activation.get("selective_macro_provider_class_delta") or {}
            ).items()
        }
    else:
        report["selective_macro_diagnostics_total"] = {
            key: sum(
                int(
                    (
                        (pair.get(args.candidate) or {}).get(
                            "selective_macro_diagnostics_delta", {}
                        )
                        or {}
                    ).get(key, 0)
                    or 0
                )
                for pair in pairs
            )
            for key in diagnostic_keys
        }
        provider_class_total = {}
        for pair in pairs:
            delta = (
                (pair.get(args.candidate) or {}).get(
                    "selective_macro_provider_class_delta", {}
                )
                or {}
            )
            for provider, count in delta.items():
                provider_class_total[provider] = (
                    provider_class_total.get(provider, 0) + count
                )
        report["selective_macro_provider_class_total"] = provider_class_total

    report["all_pairs_exact_parity"] = all(bool(pair["exact_parity"]) for pair in pairs)
    report["paired_median_deltas"] = {
        metric: summarize_paired_changes(
            paired_percent_changes(
                pairs,
                metric=metric,
                baseline_arm="off",
                candidate_arm=args.candidate,
            ),
            minimum_gain_percent=(
                args.minimum_gain_percent if metric == args.primary_metric else None
            ),
        )
        for metric in (
            "operation_completion_seconds",
            "tick_average_ms",
            "tick_p95_ms",
            "server_function_manager_execute_weighted_ms",
        )
    }
    primary_summary = report["paired_median_deltas"][args.primary_metric]
    report["performance_decision"] = primary_summary["decision"]
    # The v1 no-regression floor: the same exact interval must lie at or below
    # zero, i.e. a slowdown of the candidate is excluded. Reported for every
    # campaign alongside the promotion decision, including screening runs that
    # declare no threshold.
    report["no_regression_decision"] = primary_summary["no_regression_decision"]
    report["status"] = "complete"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"campaign complete: {report_path}", flush=True)
    print(
        f"performance_decision={report['performance_decision']} "
        f"no_regression_decision={report['no_regression_decision']} "
        f"primary_metric={args.primary_metric}",
        flush=True,
    )
    print(json.dumps(report["paired_median_deltas"], indent=2), flush=True)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stack",
        choices=(
            "fabric", "lithium", "bellows", "lm", "lb", "lbm", "lbm120",
            "bellows113", "bellows113-moonrise120", "bellows113-moonrise",
            "lb113", "lbm113", "lbm113120",
        ),
        default="fabric",
    )
    parser.add_argument("--side", type=int, choices=(4, 5, 6, 8), default=6)
    parser.add_argument(
        "--candidate",
        choices=("score-add", "selective-macro", "fused"),
        default="score-add",
    )
    parser.add_argument("--pairs", type=int)
    parser.add_argument("--seed", type=int, default=26871028)
    parser.add_argument("--capture-timeout", type=int, default=60)
    parser.add_argument("--phase", choices=("screening", "confirmatory"), default="screening")
    parser.add_argument(
        "--minimum-gain-percent",
        type=float,
        help="predeclared worthwhile primary-metric improvement; required for confirmatory runs",
    )
    parser.add_argument(
        "--primary-metric",
        choices=(
            "operation_completion_seconds",
            "tick_average_ms",
            "tick_p95_ms",
            "server_function_manager_execute_weighted_ms",
        ),
        default="operation_completion_seconds",
    )
    parser.add_argument(
        "--resume-report",
        help="resume an interrupted running campaign report using the same options",
    )
    args = parser.parse_args()
    if args.pairs is None:
        if args.phase == "confirmatory":
            parser.error("--pairs must be chosen from screening variance before a confirmatory campaign")
        args.pairs = 5
    if args.pairs < 1:
        parser.error("--pairs must be positive")
    if args.phase == "confirmatory" and args.pairs < 6:
        parser.error(
            "at least six predeclared pairs are required to attain the 95% "
            "exact median-interval confidence target"
        )
    if args.phase == "confirmatory" and args.minimum_gain_percent is None:
        parser.error("--minimum-gain-percent is required for confirmatory campaigns")
    if args.phase == "screening" and args.minimum_gain_percent is not None:
        parser.error("set the practical threshold with --phase confirmatory")
    if args.minimum_gain_percent is not None and args.minimum_gain_percent <= 0:
        parser.error("--minimum-gain-percent must be positive")
    if args.capture_timeout < 5:
        parser.error("--capture-timeout must be at least 5 seconds")
    make_report(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
