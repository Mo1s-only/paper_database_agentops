#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="${P0_ENV_FILE:?set P0_ENV_FILE to the local credential file}"
BASE_OUT="${P0_OUT_BASE:?set P0_OUT_BASE to a local results directory}"
COUNT="${P0_COUNT:-5}"

mkdir -p "${BASE_OUT}"
for index in $(seq 1 "${COUNT}"); do
    run_id="$(date -u +%Y%m%dT%H%M%SZ)_p0_pairing_pilot_$(printf '%02d' "${index}")"
    run_dir="${BASE_OUT}/${run_id}"
    echo "=== P0 pairing pilot ${index}/${COUNT}: ${run_id} ==="
    P0_ENV_FILE="${ENV_FILE}" \
      P0_OUT_DIR="${run_dir}" \
      "${ROOT}/capture_claude_http.sh"
    python3 "${ROOT}/analyze_pairing.py" --run-dir "${run_dir}"
    sleep 1
done
