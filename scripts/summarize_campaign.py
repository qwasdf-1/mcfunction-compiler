"""Print compact promotion evidence from a saved campaign report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _metric(report, key):
    data = report.get("analysis", report.get("paired_median_deltas", {}))
    for container in ("paired_median_deltas", "paired_median_deltas"):
        if isinstance(data, dict) and key in data:
            return data[key]
    if isinstance(data, dict):
        return data.get(key)
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))

    candidate = report.get("candidate")
    stack = report.get("stack")
    report_status = report.get("status")
    metric_keys = (
        "operation_completion_seconds",
        "active_tick_average_ms",
        "tick_average_ms",
        "tick_p95_ms",
    )

    print(f"report: {args.report}")
    print(f"stack: {stack}")
    print(f"candidate: {candidate}")
    print(f"status: {report_status}")

    for key in metric_keys:
        metric = _metric(report, key)
        if not metric:
            continue
        print(
            f"{key}: median={metric.get('median_percent')}% "
            f"CI=[{metric.get('ci_low_percent')}%, "
            f"{metric.get('ci_high_percent')}%] "
            f"n={metric.get('n')} "
            f"confidence={metric.get('confidence_achieved')} "
            f"decision={metric.get('decision')}"
        )

    diagnostics = report.get("selective_macro_diagnostics_total")
    if diagnostics:
        print("selective macro diagnostics total:", diagnostics)
    provider_classes = report.get("selective_macro_provider_class_total")
    if provider_classes:
        print("selective macro provider class total:", provider_classes)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
