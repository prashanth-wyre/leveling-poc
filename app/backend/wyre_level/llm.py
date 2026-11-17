"""Gemini client: JSON-schema output, file input, optional web search, disk cache, retries.

Every response is cached by a hash of (model, prompt, schema, file bytes), so re-leveling only calls the
model for inputs that changed and the app keeps working offline once a package has been leveled.
"""
import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

from . import config

_client = None
_lock = threading.Lock()
stats = {'calls': 0, 'cached': 0, 'errors': 0}


class LLMError(Exception):
    pass


def available():
    return bool(config.GEMINI_KEY)


def client():
    global _client
    with _lock:
        if _client is None:
            if not config.GEMINI_KEY:
                raise LLMError('No GEMINI_KEY set in .env')
            from google import genai
            from google.genai import types
            # a per-request timeout, so one stuck call cannot hang a whole leveling run
            _client = genai.Client(api_key=config.GEMINI_KEY, http_options=types.HttpOptions(timeout=config.LLM_TIMEOUT_S * 1000))
        return _client


def _key(kind, prompt, schema, files, extra=''):
    h = hashlib.sha256()
    for part in (kind, config.GEMINI_MODEL, prompt, json.dumps(schema, sort_keys=True) if schema else '', extra):
        h.update(part.encode())
        h.update(b'\x00')
    for mime, data in files or []:
        h.update(mime.encode())
        h.update(hashlib.sha256(data).digest())
    return h.hexdigest()


def _cache_get(key):
    f = config.CACHE / f'{key}.json'
    if f.exists():
        try:
            return json.loads(f.read_text())
        except json.JSONDecodeError:
            return None
    return None


def _cache_put(key, value):
    (config.CACHE / f'{key}.json').write_text(json.dumps(value))


def _parse_json(text):
    text = (text or '').strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r'\{.*\}', text, re.S)
        if not m:
            raise LLMError('Model did not return JSON')
        return json.loads(m.group(0))


def generate_json(prompt, schema, files=None, kind='json', use_cache=True, retries=2):
    """files: list of (mime_type, bytes). Returns the parsed JSON object."""
    key = _key(kind, prompt, schema, files)
    if use_cache:
        hit = _cache_get(key)
        if hit is not None:
            stats['cached'] += 1
            return hit
    from google.genai import types
    parts = [types.Part.from_bytes(data=d, mime_type=m) for m, d in (files or [])] + [prompt]
    cfg = types.GenerateContentConfig(temperature=0, response_mime_type='application/json', response_json_schema=schema)
    last = None
    for attempt in range(retries + 1):
        try:
            stats['calls'] += 1
            resp = client().models.generate_content(model=config.GEMINI_MODEL, contents=parts, config=cfg)
            out = _parse_json(resp.text)
            _cache_put(key, out)
            return out
        except Exception as e:  # network, quota, malformed output: retry, then surface
            last = e
            time.sleep(1.5 * (attempt + 1))
    stats['errors'] += 1
    raise LLMError(f'{type(last).__name__}: {str(last)[:300]}')


def generate_grounded_json(prompt, kind='grounded', use_cache=True):
    """Web-search grounded call. Search cannot be combined with schema output, so the JSON is asked for in the
    prompt and parsed from the text. Returns (json, sources)."""
    key = _key(kind, prompt, None, None)
    if use_cache:
        hit = _cache_get(key)
        if hit is not None:
            stats['cached'] += 1
            return hit['data'], hit['sources']
    from google.genai import types
    try:
        stats['calls'] += 1
        resp = client().models.generate_content(
            model=config.GEMINI_MODEL, contents=prompt,
            config=types.GenerateContentConfig(temperature=0, tools=[types.Tool(google_search=types.GoogleSearch())]))
        data = _parse_json(resp.text)
        sources = []
        meta = getattr(resp.candidates[0], 'grounding_metadata', None) if resp.candidates else None
        for ch in (getattr(meta, 'grounding_chunks', None) or []):
            web = getattr(ch, 'web', None)
            if web is not None and getattr(web, 'uri', None):
                sources.append({'title': getattr(web, 'title', None) or '', 'url': web.uri})
        _cache_put(key, {'data': data, 'sources': sources})
        return data, sources
    except Exception as e:
        stats['errors'] += 1
        raise LLMError(f'{type(e).__name__}: {str(e)[:300]}')


def run_parallel(fn, items, on_done=None):
    """Run fn(item) for every item on a small thread pool. Returns results in order; an exception becomes the result."""
    out = [None] * len(items)

    def work(i):
        try:
            out[i] = fn(items[i])
        except Exception as e:
            out[i] = e
        if on_done:
            on_done(i)
    with ThreadPoolExecutor(max_workers=config.LLM_WORKERS) as ex:
        list(ex.map(work, range(len(items))))
    return out
