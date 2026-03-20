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

# Layer 0: Import check
run_step "Import all modules" uv run python -c "
import localwhisper.config
import localwhisper.history
import localwhisper.postprocessor
import localwhisper.transcriber
import localwhisper.recorder
import localwhisper.clipboard
import localwhisper.hotkey
import localwhisper.sounds
import localwhisper.feedback
import localwhisper.app
print('All imports OK')
"

# Layer 0: Quick tests
run_step "Quick checks" uv run python -m pytest tests/test_quick.py -x -q --timeout=10 --tb=short

# Layer 1: Unit tests
run_step "Unit tests" uv run python -m pytest tests/test_unit.py -x -q --timeout=30 --tb=short

# Layer 2: Integration tests
if [[ "${1:-}" == "--full" ]]; then
    run_step "Integration tests (full)" uv run python -m pytest tests/test_integration.py -x -q --timeout=180 --run-slow --tb=short
else
    run_step "Integration tests (quick)" uv run python -m pytest tests/test_integration.py -x -q -m "integration and not slow" --timeout=60 --tb=short
fi

# Summary
echo "================================"
if [ $FAILED -eq 0 ]; then
    printf "${GREEN}All checks passed${NC}\n"
else
    printf "${RED}Some checks failed${NC}\n"
    exit 1
fi
