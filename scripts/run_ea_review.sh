#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEFAULT_EA_ROOT="${PROJECT_ROOT}/../../engineering-auditor/.worktree-v1.5.0"
if [[ -n "${FC_ENGINEERING_AUDITOR_ROOT:-}" ]]; then
    EA_ROOT="${FC_ENGINEERING_AUDITOR_ROOT}"
elif [[ -n "${FC_ENGINEERING_AUDITOR_BIN:-}" ]]; then
    EA_ROOT="$(cd "$(dirname "${FC_ENGINEERING_AUDITOR_BIN}")/../.." && pwd)"
else
    EA_ROOT="${DEFAULT_EA_ROOT}"
fi
EA_BIN="${FC_ENGINEERING_AUDITOR_BIN:-${EA_ROOT}/target/release/auditor}"
EXPECTED_VERSION="1.5.0"
EXPECTED_COMMIT="d014177acf6b3c3cefc425252229d81fbea62150"
REPORT_DIR="${PROJECT_ROOT}/build/reports/engineering-auditor/v1.5.0"
REPORT_PATH="${REPORT_DIR}/report.json"

if [[ ! -x "${EA_BIN}" ]]; then
    echo "Engineering Auditor v${EXPECTED_VERSION} not found at ${EA_BIN}" >&2
    echo "Set FC_ENGINEERING_AUDITOR_ROOT or FC_ENGINEERING_AUDITOR_BIN to the pinned worktree." >&2
    exit 2
fi

EA_VERSION="$("${EA_BIN}" --version)"
if [[ "${EA_VERSION}" != "${EXPECTED_VERSION}" ]]; then
    echo "Engineering Auditor version mismatch: expected ${EXPECTED_VERSION}, got ${EA_VERSION}" >&2
    exit 2
fi

EA_CHECKOUT="${EA_ROOT}"
EA_COMMIT="$(git -C "${EA_CHECKOUT}" rev-parse HEAD)"
if [[ "${EA_COMMIT}" != "${EXPECTED_COMMIT}" ]]; then
    echo "Engineering Auditor commit mismatch: expected ${EXPECTED_COMMIT}, got ${EA_COMMIT}" >&2
    exit 2
fi

mkdir -p "${REPORT_DIR}"
"${EA_BIN}" scan \
    --repo-root "${PROJECT_ROOT}" \
    --profile gating \
    --format json \
    --output "${REPORT_PATH}" \
    --quiet

python3 - "${REPORT_PATH}" <<'PY'
import collections
import json
import sys

report = json.loads(open(sys.argv[1], encoding="utf-8").read())
counts = collections.Counter(item["severity"] for item in report["findings"])
print(f"Report schema: v{report['schema_version']}")
print(f"Findings: {len(report['findings'])}; by severity: {dict(sorted(counts.items()))}")
print(f"Report: {sys.argv[1]}")
PY
