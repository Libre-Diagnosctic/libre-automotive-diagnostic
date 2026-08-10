#!/usr/bin/env bash
# ============================================================================
#  K-OBD-PI AUTOMOTIVE - Developer Helper
#  One-shot: build everything, clean artifacts and stage a deployment bundle.
# ============================================================================
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

echo "=== K-OBD-PI Build Helper ==="

if [[ "${1:-}" == "clean" ]]; then
    echo "--- Cleaning build artifacts ---"
    make clean >/dev/null 2>&1 || true
    rm -f obd_app obd_cli can_raw_receiver obd_user_app secure_server
    echo "Clean complete."
    exit 0
fi

echo "--- Compiling user-space gateway + tools ---"
make gateway tools

echo "--- Optional: kernel module (requires kernel headers) ---"
if [[ -d "/lib/modules/$(uname -r)/build" ]]; then
    make module
else
    echo "Skipping kernel module: /lib/modules/$(uname -r)/build not found."
fi

echo "--- Staging deployable bundle ---"
BUNDLE="deploy/$(date +%Y%m%d-%H%M%S)"
mkdir -p "${BUNDLE}"
cp -f obd_app obd_cli obd_user_app can_raw_receiver 2>/dev/null || true
cp -f driver/obd_driver.ko 2>/dev/null || true
cp -f scripts/start_obd.sh "${BUNDLE}/"
echo "Bundle staged at: ${BUNDLE}"
echo "Done."
