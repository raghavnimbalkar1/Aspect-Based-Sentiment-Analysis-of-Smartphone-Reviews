#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/absa || ! -f frontend/dist/index.html ]]; then
  echo "Run 'make setup build' before starting the application."
  exit 1
fi
echo "Open http://localhost:8000 in your browser. Press Ctrl+C to stop."
exec .venv/bin/absa serve
