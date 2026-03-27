#!/bin/bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

FAILED=0

run_step() {
    local name="$1"
    shift
    printf "${YELLOW}--- %s ---${NC}\n" "$name"
    if "$@"; then
        printf "${GREEN}PASS: %s${NC}\n\n" "$name"
    else
        printf "${RED}FAIL: %s${NC}\n\n" "$name"
        FAILED=1
    fi
}

run_step "Ruff" uv run ruff check .

run_step "Unit tests" uv run python -m pytest tests/ --ignore=tests/test_integration.py -x -q --timeout=30 --tb=short

if [[ "${1:-}" == "--full" ]]; then
    run_step "Integration tests" uv run python -m pytest tests/test_integration.py -x -q --timeout=180 --run-slow --tb=short
fi

echo "================================"
if [ $FAILED -eq 0 ]; then
    printf "${GREEN}All checks passed${NC}\n"
else
    printf "${RED}Some checks failed${NC}\n"
    exit 1
fi
