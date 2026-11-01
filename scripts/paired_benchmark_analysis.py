#!/usr/bin/env python3
"""Shared paired-trial analysis for Function Compiler benchmark campaigns."""

from __future__ import annotations

import statistics
from math import comb


def _median_interval(
    changes: list[float], confidence: float
) -> tuple[float, float, float, int]:
    ordered = sorted(changes)
    count = len(ordered)
    selected_order = 1
    achieved = 1.0 - 2.0 / (2**count)
    for order in range(1, (count + 1) // 2 + 1):
        excluded_tail = sum(comb(count, index) for index in range(order))
        coverage = 1.0 - (2.0 * excluded_tail / (2**count))
        if coverage + 1e-12 >= confidence:
            selected_order = order
            achieved = coverage
        else:
            break
    return (
        ordered[selected_order - 1],
        ordered[count - selected_order],
        achieved,
        selected_order,
    )


def paired_percent_changes(
    pairs: list[dict[str, object]],
    *,
    metric: str,
    baseline_arm: str,
    candidate_arm: str,
) -> list[float]:
    """Return paired candidate-vs-baseline percent changes; negative is faster."""
    changes: list[float] = []
    for index, pair in enumerate(pairs, start=1):
        baseline = pair.get(baseline_arm)
        candidate = pair.get(candidate_arm)
        if not isinstance(baseline, dict) or not isinstance(candidate, dict):
            raise ValueError(f"Pair {index} is missing {baseline_arm!r} or {candidate_arm!r}")
        baseline_value = baseline.get(metric)
        candidate_value = candidate.get(metric)
        if baseline_value is None and candidate_value is None:
            continue
        if not isinstance(baseline_value, (int, float)) or not isinstance(candidate_value, (int, float)):
            raise ValueError(f"Pair {index} has no numeric {metric!r} value")
        if baseline_value <= 0:
            raise ValueError(f"Pair {index} baseline {metric!r} must be positive")
        changes.append((float(candidate_value) / float(baseline_value) - 1.0) * 100.0)
    return changes


def summarize_paired_changes(
    changes: list[float],
    *,
    minimum_gain_percent: float | None = None,
    confidence: float = 0.95,
) -> dict[str, float | int | str | None]:
    """Summarize paired percent changes and optionally apply a predeclared threshold.

    The exact sign/order-statistic interval is distribution-free for the median
    paired change. Its achieved coverage is discrete, so the actual value is
    reported instead of being rounded up to the requested confidence.
    """
    if not changes:
        return {
            "n": 0,
            "median_percent": None,
            "min_percent": None,
            "max_percent": None,
            "confidence_target": confidence,
            "confidence_achieved": None,
            "ci_low_percent": None,
            "ci_high_percent": None,
            "ci_method": "exact sign/order-statistic interval for median paired percent change",
            "decision": "insufficient_pairs",
        }
    if not 0.0 < confidence < 1.0:
        raise ValueError("confidence must be between 0 and 1")
    if minimum_gain_percent is not None and minimum_gain_percent <= 0:
        raise ValueError("minimum_gain_percent must be positive")

    ci_low, ci_high, achieved, order = _median_interval(changes, confidence)

    if len(changes) < 2:
        decision = "insufficient_pairs"
    elif minimum_gain_percent is None:
        decision = "screening_only"
    elif achieved + 1e-12 < confidence:
        decision = "inconclusive"
    elif ci_high <= -minimum_gain_percent:
        decision = "meets_threshold"
    elif ci_low > -minimum_gain_percent:
        decision = "does_not_meet_threshold"
    else:
        decision = "inconclusive"

    return {
        "n": len(changes),
        "median_percent": statistics.median(changes),
        "min_percent": min(changes),
        "max_percent": max(changes),
        "confidence_target": confidence,
        "confidence_achieved": achieved,
        "ci_low_percent": ci_low,
        "ci_high_percent": ci_high,
        "ci_method": "exact sign/order-statistic interval for median paired percent change",
        "interval_order": order,
        "minimum_gain_percent": minimum_gain_percent,
        "decision": decision,
    }
