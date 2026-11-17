"""AI market-price plugs: Gemini on Vertex AI with Google Search grounding, cached as snapshots.

Credentials come from the environment only and are never written to disk:
  GOOGLE_API_KEY                       Vertex AI API key, or
  GOOGLE_CLOUD_PROJECT + GOOGLE_CLOUD_LOCATION (+ gcloud application-default login)
  GEMINI_MODEL                         optional, default below

The prompt is generic (item, unit, region, date). No project, bidder or user details are sent.
"""
import datetime
import json
import os
import re

DEFAULT_MODEL = 'gemini-3.5-flash'

PROMPT = """You are a construction cost estimator. Using current web sources, find the typical installed
(material + labor) price for: {what}.
Region: {region}. Only use sources published in the last {months} months (today is {today}).
Reply with ONLY a JSON object, no prose, with these keys:
  "unit_price": number, typical price per {unit} in USD,
  "low": number, "high": number,
  "unit": "{unit}",
  "confidence": "high" | "medium" | "low",
  "basis": one sentence on how the figure was derived,
  "sources": [{{"title": str, "url": str, "published": "YYYY-MM or unknown"}}]
If you cannot find at least two usable sources, set "confidence" to "low"."""


def credentials_present():
    return bool(os.environ.get('GOOGLE_API_KEY') or os.environ.get('GOOGLE_CLOUD_PROJECT'))


def _client():
    from google import genai
    key = os.environ.get('GOOGLE_API_KEY')
    if key:
        try:
            return genai.Client(vertexai=True, api_key=key)      # Vertex AI with an API key
        except Exception:
            return genai.Client(api_key=key)
    return genai.Client(vertexai=True, project=os.environ['GOOGLE_CLOUD_PROJECT'],
                        location=os.environ.get('GOOGLE_CLOUD_LOCATION', 'global'))


def ask(client, what, unit, cfg, today):
    from google.genai.types import GenerateContentConfig, GoogleSearch, Tool
    model = os.environ.get('GEMINI_MODEL', DEFAULT_MODEL)
    prompt = PROMPT.format(what=what, region=cfg['region'], months=cfg['recency_months'], today=today, unit=unit)
    snap = dict(query=what, unit=unit, region=cfg['region'], model=model, asked_on=str(today))
    try:
        resp = client.models.generate_content(model=model, contents=prompt,
                                              config=GenerateContentConfig(tools=[Tool(google_search=GoogleSearch())], temperature=0))
        text = resp.text or ''
        m = re.search(r'\{.*\}', text, re.S)
        data = json.loads(m.group(0)) if m else {}
        grounded = []
        meta = getattr(resp.candidates[0], 'grounding_metadata', None) if resp.candidates else None
        for ch in (getattr(meta, 'grounding_chunks', None) or []):
            web = getattr(ch, 'web', None)
            if web and getattr(web, 'uri', None):
                grounded.append(dict(title=getattr(web, 'title', None), url=web.uri))
        snap.update(unit_price=data.get('unit_price'), low=data.get('low'), high=data.get('high'),
                    confidence=data.get('confidence', 'low'), basis=data.get('basis'),
                    sources=data.get('sources') or grounded, grounding_chunks=grounded, raw_text=text[:4000])
    except Exception as e:                                       # recorded, so the fallback chain is exercised
        snap.update(error=f'{type(e).__name__}: {e}'[:500], unit_price=None, sources=[], confidence='low')
    return snap


def load_or_fetch(path, queries, items_by_pkg, cfg, refresh=False):
    """Return {'pkg/item': snapshot}. Fetch missing ones when credentials exist; otherwise reuse what is on disk."""
    snaps = json.loads(path.read_text()) if path.exists() else {}
    todo = [(p, k) for (p, k) in queries if refresh or f'{p}/{k}' not in snaps]
    status = 'snapshots reused'
    if todo and credentials_present():
        client, today = _client(), datetime.date.today()
        for p, k in todo:
            snaps[f'{p}/{k}'] = ask(client, queries[(p, k)], items_by_pkg[p][k]['unit'], cfg, today)
        status = f'{len(todo)} item(s) queried live'
    elif todo:
        status = f'PENDING: {len(todo)} item(s) have no snapshot and no credentials are set; fallback methods used'
    return snaps, status
