#!/usr/bin/env bash
# ==============================================================================
# Sovereign On-Premise Agentic AI Workbench — Air-Gapped Bootstrap Wrapper (Bash)
# Runs scripts/bootstrap.py to prepare offline database, vectors, and audit ledger.
# ==============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
python3 "${SCRIPT_DIR}/bootstrap.py"
