"""AI extraction: read a bid (PDF, Word, Excel) against the baseline items; read a scope sheet into baseline items."""
import json
import re

from .. import ingest, llm

NUM = {'type': ['number', 'null']}
STR = {'type': ['string', 'null']}

BID_SCHEMA = {
    'type': 'object',
    'properties': {
        'doc_type': {'type': 'string', 'enum': ['bid', 'decline', 'not_a_bid']},
        'bidder_name': STR, 'bid_date': STR, 'reference': STR,
        'is_revision': {'type': 'boolean'}, 'supersedes_note': STR,
        'stated_total': NUM,
        'items': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {
                'scope_key': {'type': 'string'},
                'status': {'type': 'string', 'enum': ['priced', 'included', 'excluded', 'not_mentioned']},
                'bid_description': STR, 'quantity': NUM, 'unit': STR, 'unit_price': NUM, 'amount': NUM,
                'depth_in': NUM, 'unit_note': STR,
                'gc_units_per_bid_unit': NUM, 'conversion_explanation': STR,
                'source_snippet': STR, 'confidence': {'type': 'number'}, 'note': STR,
            },
            'required': ['scope_key', 'status', 'confidence'],
        }},
        'extra_lines': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'description': {'type': 'string'}, 'amount': NUM,
                           'treatment': {'type': 'string', 'enum': ['add', 'credit', 'alternate', 'allowance', 'info']},
                           'source_snippet': STR},
            'required': ['description', 'treatment'],
        }},
        'inclusions': {'type': 'array', 'items': {'type': 'string'}},
        'exclusions': {'type': 'array', 'items': {'type': 'string'}},
        'clarifications': {'type': 'array', 'items': {'type': 'string'}},
        'alternates': {'type': 'array', 'items': {'type': 'object', 'properties': {'description': {'type': 'string'}, 'amount': NUM}, 'required': ['description']}},
        'warranty': {'type': 'array', 'items': {'type': 'string'}},
        'validity_days': NUM,
        'addenda_acknowledged': {'type': 'array', 'items': {'type': 'string'}},
        'tax': {'type': 'string', 'enum': ['included', 'excluded', 'not_stated']},
        'tax_note': STR,
        'red_flags': {'type': 'array', 'items': {'type': 'string'}},
    },
    'required': ['doc_type', 'bidder_name', 'items', 'extra_lines', 'inclusions', 'exclusions', 'warranty', 'tax'],
}

BID_PROMPT = """You are a construction estimator leveling subcontractor bids for a general contractor.
Read the attached subcontractor document and extract it against the GC's baseline scope items.

BASELINE SCOPE ITEMS (the GC's list; `unit` is the GC's unit of measure):
{scope}

Rules:
- First decide doc_type: "bid" (it prices work), "decline" (the firm says it will not bid), or "not_a_bid".
- Return exactly one entry in `items` for EVERY baseline item key above, in the same order.
- status:
  "priced"        the bid gives its own dollar amount for this item
  "included"      the bid says the item is included in another line or in its price, with no separate amount
  "excluded"      the bid explicitly excludes it, says "by others", "not included", or similar
  "not_mentioned" the bid is silent about it
- Copy quantity, unit, unit_price and amount exactly as written in the bid. Never calculate, round or convert them.
  A lump sum has amount only. If a quantity is shown without a unit price, leave unit_price null.
- If one bid line covers several baseline items, put the amount on the main item and mark the others "included",
  saying so in `note`.
- depth_in: the depth in inches the bidder states for bulk material (mulch, rock, topsoil), if any.
- unit_note: any stated size assumption (roll size, panel length, waste allowance, "own takeoff").
- gc_units_per_bid_unit: when the bid's unit differs from the GC unit, how many GC units ONE bid unit equals,
  using the bid's own stated assumptions (for example 1 roofing square = 100 SF, 1 SY = 9 SF, 1 m2 = 10.7639 SF,
  1 CY at 3 in. depth = 108 SF, one 10 SF sod roll = 10 SF, one 8 ft panel = 8 LF). Give the reasoning in
  conversion_explanation. Null when units match or the conversion cannot be determined.
- source_snippet: the exact text from the document that supports the entry (at most 160 characters).
- confidence: 0 to 1, how sure you are that the entry is right.
- extra_lines: every priced line that does NOT belong to a baseline item (mobilization, freight, supervision,
  credits, tax, allowances the bidder adds). treatment: "add" if it is part of the bid total, "credit" if it reduces
  the total (give the amount as a positive number), "alternate" if priced separately and not in the total,
  "allowance" or "info" otherwise.
- stated_total: the bid total as written. Do not add it up yourself.
- is_revision / supersedes_note: true when the document says it revises or supersedes an earlier quote.
- inclusions, exclusions, clarifications, warranty, addenda_acknowledged: short strings in the bidder's words.
- validity_days: how long the price is valid, in days, if stated.
- tax: whether sales tax is included in the prices.
- red_flags: anything an estimator must check (totals that do not add up, scope the bidder will not split,
  missing addenda, unusual assumptions).
- bid_date in YYYY-MM-DD.
{doc}"""

SCOPE_SCHEMA = {
    'type': 'object',
    'properties': {
        'package_name': STR,
        'items': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'key': {'type': 'string'}, 'name': {'type': 'string'}, 'section': {'type': 'string'},
                           'unit': STR, 'qty': NUM, 'rate': NUM, 'estimate': NUM, 'depth': NUM, 'spec': STR},
            'required': ['key', 'name', 'section'],
        }},
    },
    'required': ['items'],
}

SCOPE_PROMPT = """You are a construction estimator. The text below is a GC scope sheet for one bid package.
Turn it into the list of baseline scope items that subcontractors must price.

Rules:
- One entry per item that is to be PRICED. Skip instructions, bid-form requirements, warranty tables and
  acknowledgement lists. Items the sheet marks as "Confirm" only (no price) are skipped.
- key: a short unique code. Use the sheet's own key if it has one; otherwise make one from the name
  (uppercase letters and digits, at most 10 characters).
- section: group items into 2 to 6 sensible sections using the sheet's headings or the nature of the work.
- unit and qty: the GC's unit of measure and takeoff quantity, when given. Use LS for lump sum items.
- rate and estimate: the GC's own unit rate and estimate for the item, when the sheet (for example a confidential
  estimate tab) gives them for that same item. Otherwise null. Do not invent them.
- depth: specified depth in inches for bulk material, when given.

SCOPE SHEET:
{doc}"""


def scope_block(items):
    lines = []
    for it in items:
        extra = f", specified depth {it['depth']:g} in." if it.get('depth') else ''
        lines.append(f"- {it['key']}: {it['name']} [section: {it.get('section', '')}; unit: {it.get('unit') or 'LS'}{extra}]")
    return '\n'.join(lines)


def extract_bid(path, items, use_cache=True):
    """Returns the extraction dict (BID_SCHEMA) with `cells` keyed by scope key added for convenience."""
    doc = ingest.read(path)
    body = '' if doc['files'] else f"\nDOCUMENT TEXT:\n{doc['text'][:120000]}"
    out = llm.generate_json(BID_PROMPT.format(scope=scope_block(items), doc=body), BID_SCHEMA, files=doc['files'], kind='extract_bid', use_cache=use_cache)
    keys = {it['key'] for it in items}
    cells = {}
    for e in out.get('items') or []:
        k = e.get('scope_key')
        if k in keys and k not in cells:
            cells[k] = e
    for k in keys - cells.keys():
        cells[k] = {'scope_key': k, 'status': 'not_mentioned', 'confidence': 0.3, 'note': 'Not returned by the extraction'}
    out['cells'] = cells
    out['bidder_name'] = tidy_name(out.get('bidder_name'))
    reconcile(out)
    return out


def reconcile(ext):
    """If the lines read fall short of the stated total by exactly the amount of some lines the model put outside the
    total (allowance or info), those lines are part of the bid: count them. Then rerun the arithmetic checks."""
    from itertools import combinations
    arithmetic_checks(ext)
    st, lt = ext.get('stated_total'), ext.get('lines_total')
    if st is None or lt is None or abs(st - lt) <= 1:
        return ext
    loose = [e for e in ext.get('extra_lines') or [] if e.get('treatment') in ('allowance', 'info') and e.get('amount')]
    for n in range(1, min(4, len(loose)) + 1):
        for combo in combinations(loose, n):
            if abs(sum(e['amount'] for e in combo) - (st - lt)) <= 1:
                for e in combo:
                    e['treatment'] = 'add'
                    e['reconciled'] = 'Counted in the bid total: the lines add up to the stated total only with this line included'
                arithmetic_checks(ext)
                return ext
    return ext


def arithmetic_checks(ext):
    """Deterministic checks on what was read: do the lines add up to the stated total?"""
    checks = []
    total = 0.0
    for c in ext['cells'].values():
        if c.get('status') == 'priced' and c.get('amount') is not None:
            total += c['amount']
    for e in ext.get('extra_lines') or []:
        if e.get('amount') is None:
            continue
        if e['treatment'] == 'add':
            total += e['amount']
        elif e['treatment'] == 'credit':
            total -= abs(e['amount'])
    ext['lines_total'] = round(total, 2)
    ext['checks'] = checks
    st = ext.get('stated_total')
    if st is not None and abs(st - total) > max(1.0, 0.0002 * abs(st)):
        checks.append(f'Lines read add up to ${total:,.2f} but the bid states a total of ${st:,.2f} (difference ${st - total:,.2f})')
    return checks


def extract_scope(path):
    doc = ingest.read(path)
    out = llm.generate_json(SCOPE_PROMPT.format(doc=doc['text'][:120000]), SCOPE_SCHEMA, files=doc['files'], kind='extract_scope')
    items, seen = [], set()
    for it in out.get('items') or []:
        key = re.sub(r'[^A-Z0-9_]', '', (it.get('key') or '').upper())[:12] or f'ITEM{len(items) + 1}'
        while key in seen:
            key += 'X'
        seen.add(key)
        unit = (it.get('unit') or 'LS').upper()
        qty, rate, est = it.get('qty'), it.get('rate'), it.get('estimate')
        if est is None and qty and rate:
            est = round(qty * rate, 2)
        if rate is None and qty and est:
            rate = round(est / qty, 4)
        items.append({'key': key, 'name': it['name'], 'section': it.get('section') or 'General', 'unit': unit,
                      'qty': qty if unit != 'LS' else None, 'rate': rate, 'estimate': est, 'depth': it.get('depth'), 'spec': it.get('spec')})
    return items


def norm_name(name):
    s = re.sub(r'[^a-z0-9 ]', ' ', (name or '').lower())
    s = re.sub(r'\b(inc|llc|co|corp|corporation|company|ltd|the)\b', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def tidy_name(name):
    """A letterhead in capitals (SAGEBRUSH SURFACES) becomes Sagebrush Surfaces; mixed-case names are left alone."""
    if not name or name != name.upper() or len(name) < 5:
        return name
    small = {'and', 'of', 'the', '&'}
    keep = {'LLC', 'INC', 'LLP', 'USA', 'CO', 'LTD'}
    words = [w if w.strip('.,') in keep else (w.lower() if w.lower() in small and i else w.capitalize()) for i, w in enumerate(name.split())]
    return ' '.join(words)


def summarize(ext):
    """Compact text of the non-price content of a bid, for the assessment prompt."""
    return json.dumps({k: ext.get(k) for k in ('inclusions', 'exclusions', 'clarifications', 'warranty', 'validity_days',
                                               'addenda_acknowledged', 'tax', 'tax_note', 'red_flags', 'alternates')}, indent=1)
