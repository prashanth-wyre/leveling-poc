"""Paths and settings. Secrets come from the repo-level .env and are never written anywhere else."""
import os
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
DATA = Path(os.environ.get('WYRE_DATA_DIR', REPO / 'app' / 'data'))
UPLOADS = DATA / 'uploads'
CACHE = DATA / 'llm_cache'
DB_PATH = DATA / 'wyre.db'
SAMPLES = REPO / 'samples'


def _load_env():
    f = REPO / '.env'
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        m = re.match(r'\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)\s*$', line)
        if m and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


_load_env()
GEMINI_KEY = os.environ.get('GEMINI_KEY') or os.environ.get('GOOGLE_API_KEY') or ''
GEMINI_MODEL = os.environ.get('GEMINI_MODEL') or 'gemini-3.5-flash'
LLM_WORKERS = int(os.environ.get('WYRE_LLM_WORKERS', '6'))
LLM_TIMEOUT_S = int(os.environ.get('WYRE_LLM_TIMEOUT_S', '180'))

for d in (DATA, UPLOADS, CACHE):
    d.mkdir(parents=True, exist_ok=True)
