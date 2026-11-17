#!/bin/bash
# Build the front end and start the app on http://localhost:8000
#   ./app/run.sh           build + serve
#   ./app/run.sh --dev     API on :8000 and Vite dev server with hot reload on :5173
set -e
cd "$(dirname "$0")"
if [ ! -d frontend/node_modules ]; then (cd frontend && npm install --no-audit --no-fund); fi
if [ "$1" = "--dev" ]; then
  (cd backend && uv run uvicorn wyre_level.main:app --port 8000 --reload) &
  trap 'kill %1' EXIT
  cd frontend && npm run dev
else
  (cd frontend && npm run build)
  cd backend && exec uv run uvicorn wyre_level.main:app --port 8000
fi
