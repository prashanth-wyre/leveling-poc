#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
exec simulator/.venv/bin/streamlit run simulator/app.py --server.address 127.0.0.1 "$@"
