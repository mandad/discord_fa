#!/usr/bin/env bash
# Fetch ship-position.py from the private mandad/life-manager repo using GitHub auth.
# Uses the `gh` CLI, which honors either a prior `gh auth login` or a GH_TOKEN / GITHUB_TOKEN
# env var. Works the same locally and on the VM.
#
# Usage:  ./fetch-ship-position.sh [output_path]      (default: ./ship-position.py)
#   override source via env: SHIP_REPO, SHIP_REF, SHIP_PATH
set -euo pipefail

SHIP_REPO="${SHIP_REPO:-mandad/life-manager}"
SHIP_REF="${SHIP_REF:-master}"
SHIP_PATH="${SHIP_PATH:-scripts/ship-position.py}"
OUT="${1:-ship-position.py}"

if ! command -v gh >/dev/null 2>&1; then
  echo "error: gh (GitHub CLI) not installed" >&2
  exit 1
fi
if ! gh auth status >/dev/null 2>&1 && [ -z "${GH_TOKEN:-}${GITHUB_TOKEN:-}" ]; then
  echo "error: not authenticated. Run 'gh auth login' or export GH_TOKEN." >&2
  exit 1
fi

gh api "repos/${SHIP_REPO}/contents/${SHIP_PATH}?ref=${SHIP_REF}" \
  -H "Accept: application/vnd.github.raw" > "$OUT"
echo "wrote $OUT  <-  ${SHIP_REPO}@${SHIP_REF}:${SHIP_PATH}"
