#!/usr/bin/env bash
set -eu
cd "$(dirname "$0")/.."
uv venv --allow-existing --python 3.12 simulator/.venv
uv pip install --python simulator/.venv/bin/python -r app/backend/pyproject.toml -r simulator/requirements.txt
