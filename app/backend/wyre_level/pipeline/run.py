"""One leveling run for a package: extract -> ordinals -> normalize and plug -> assess and score -> explain -> save."""
import hashlib
import json
import statistics
import threading
import time
import traceback

from .. import db, engine, ingest, llm
from . import assess, explain, extract, policy as policy_mod

RUNS = {}
_lock = threading.Lock()
STEPS = ['Reading proposals', 'Reading the award policy', 'Normalizing units and quantities', 'Estimating plugs',
         'Scoring against the policy', 'Writing explanations', 'Saving']


def _set(pid, **kw):
    with _lock:
        RUNS.setdefault(pid, {}).update(kw)


def status(pid):
    with _lock:
        r = RUNS.get(pid)
        return dict(r) if r else None


def bidder_id(name):
    return 'b_' + hashlib.sha1(extract.norm_name(name).encode()).hexdigest()[:8]


def code_for(i):
    return chr(65 + i) if i < 26 else chr(64 + i // 26) + chr(65 + i % 26)


def scope_hash(items):
    return hashlib.sha1(json.dumps([(i['key'], i['name'], i.get('unit'), i.get('depth')) for i in items]).encode()).hexdigest()[:12]


def support_text(docs):
    out = []
    for d in docs:
        if d['kind'] != 'supporting' or not d.get('path'):
            continue
        try:
            out.append(f"--- {d['filename']} ---\n" + ingest.read(d['path'])['text'][:8000])
        except Exception:
            continue
    return '\n\n'.join(out)[:24000]


def policy_text(docs):
    for d in docs:
        if d['kind'] == 'award_policy' and d.get('path'):
            # prefer a text version when both .md and .docx were uploaded
            pass
    cands = sorted((d for d in docs if d['kind'] == 'award_policy' and d.get('path')), key=lambda d: (not d['filename'].endswith('.md'), d['filename']))
    return ingest.read(cands[0]['path'])['text'] if cands else None


def generate_policy(pid):
    """Read the award policy document and store the ordinals. Returns the policy."""
    docs = db.many('SELECT * FROM documents WHERE package_id=?', (pid,))
    text = policy_text(docs)
    if not text:
        pol = json.loads(json.dumps(policy_mod.DEFAULT_POLICY))
    else:
        try:
            pol = policy_mod.generate(text)
        except llm.LLMError as e:
            pol = json.loads(json.dumps(policy_mod.DEFAULT_POLICY))
            pol['summary'] = f'The award policy could not be read ({e}). Default ordinals are in use.'
    db.update('packages', pid, policy=pol)
    return pol


def start(pid, force_extract=False):
    cur = status(pid)
    if cur and cur.get('status') == 'running':
        return cur
    _set(pid, status='running', step=STEPS[0], stepIndex=0, steps=STEPS, done=0, total=0, message='', startedAt=time.time(), error=None)
    threading.Thread(target=_guarded, args=(pid, force_extract), daemon=True).start()
    return status(pid)


def _guarded(pid, force_extract):
    try:
        level_package(pid, force_extract)
        _set(pid, status='done', finishedAt=time.time())
    except Exception as e:
        traceback.print_exc()
        _set(pid, status='error', error=f'{type(e).__name__}: {e}', finishedAt=time.time())


def _limit_flags(items, rows, bidders, row_share=0.34, cell_share=0.12):
    """A dot on everything says nothing. Keep the flags the numbers back most strongly: about a third of scope items
    and about one cell in eight. Reading checks (arithmetic, conversions) always keep their flag."""
    def row_score(k):
        r = rows[k]
        spread = (r['q3'] - r['q1']) / r['med'] if r['n'] >= 3 and r['med'] else 0
        return spread + 1.5 * r['plugged'] / max(1, len(bidders)) + 0.5 * (r['unitNormalized'] + r['qtyNormalized']) / max(1, len(bidders))
    flagged = sorted((k for k in rows if rows[k]['note']['flag']), key=row_score, reverse=True)
    for k in flagged[max(1, round(len(items) * row_share)):]:
        rows[k]['note']['flag'] = False
    cells = []
    for b in bidders:
        for k, c in b['cells'].items():
            if not c['note']['flag']:
                continue
            if any(not f.startswith('Lump sum') for f in c.get('flags') or []):
                continue                                   # a reading check: always shown
            s = abs(c.get('dev') or 0)
            if c['state'] == 'plugged' and b['leveledTotal']:
                s += 3 * c['value'] / b['leveledTotal']
            if c.get('qtyNorm') and c['qtyNorm']['applied']:
                s += abs(c['qtyNorm']['variancePct']) / 100
            cells.append((s, c))
    cells.sort(key=lambda x: -x[0])
    for _, c in cells[max(1, round(len(items) * len(bidders) * cell_share)):]:
        c['note']['flag'] = False


def level_package(pid, force_extract=False):
    settings = db.one('SELECT settings FROM packages WHERE id=?', (pid,))['settings'] or {}
    token = llm.stage_models.set(settings.get('stage_models', {}))
    try:
        return _level_package(pid, force_extract)
    finally:
        llm.stage_models.reset(token)


def _level_package(pid, force_extract=False):
    t0 = time.time()
    calls0 = dict(llm.stats)
    pkg = db.one('SELECT * FROM packages WHERE id=?', (pid,))
    proj = db.one('SELECT * FROM projects WHERE id=?', (pkg['project_id'],))
    scope = pkg['scope'] or {'items': []}
    items = scope['items']
    if not items:
        raise ValueError('This package has no baseline items yet. Add them on the Scopes page first.')
    docs = db.many('SELECT * FROM documents WHERE package_id=? ORDER BY uploaded_at', (pid,))
    sh = scope_hash(items)

    # 1. extraction ------------------------------------------------------------------------------------
    todo = [d for d in docs if d['kind'] == 'bid' and d.get('path') and (force_extract or d.get('status')=='error' or not d.get('extraction') or d['extraction'].get('scope_hash') != sh)]
    _set(pid, step=STEPS[0], stepIndex=0, done=0, total=len(todo), message=f'{len(todo)} to read' if todo else 'Using earlier readings')

    def do_extract(d):
        ext = extract.extract_bid(d['path'], items, use_cache=not force_extract)
        ext['scope_hash'] = sh
        return ext
    done = [0]

    def tick(_i):
        done[0] += 1
        _set(pid, done=done[0])
    for d, ext in zip(todo, llm.run_parallel(do_extract, todo, tick)):
        if isinstance(ext, Exception):
            db.update('documents', d['id'], status='error', error=str(ext)[:400], extraction=None)
        else:
            st = {'bid': 'extracted', 'decline': 'declined'}.get(ext.get('doc_type'), 'not_a_bid')
            db.update('documents', d['id'], status=st, error=None, extraction=ext)
    docs = db.many('SELECT * FROM documents WHERE package_id=? ORDER BY uploaded_at', (pid,))

    groups, declined = {}, []
    for d in docs:
        ext = d.get('extraction')
        if d['kind'] != 'bid' or not ext:
            continue
        name = ext.get('bidder_name') or d['filename']
        if ext.get('doc_type') == 'decline':
            declined.append({'name': name, 'filename': d['filename'], 'documentId': d['id']})
        elif ext.get('doc_type') == 'bid':
            groups.setdefault(extract.norm_name(name), []).append(d)
    current, superseded = [], []
    for g in groups.values():
        g.sort(key=lambda d: (d['extraction'].get('bid_date') or '', d['uploaded_at']))
        current.append(g[-1])
        for old in g[:-1]:
            superseded.append({'name': old['extraction'].get('bidder_name'), 'filename': old['filename'], 'documentId': old['id'],
                               'date': old['extraction'].get('bid_date'), 'total': old['extraction'].get('stated_total') or old['extraction'].get('lines_total'),
                               'supersededBy': g[-1]['filename']})
    current.sort(key=lambda d: d['uploaded_at'])
    if not current:
        raise ValueError('No proposals could be read for this package. Upload at least one bid.')

    # 2. ordinals --------------------------------------------------------------------------------------
    _set(pid, step=STEPS[1], stepIndex=1, done=0, total=1, message='')
    pol = pkg['policy'] or generate_policy(pid)
    if 'award_rule' not in pol:                          # ordinals stored before the award rule was read
        pol['award_rule'] = policy_mod.award_rule(policy_text(docs))
        db.update('packages', pid, policy=pol)

    # 3 + 4. normalize, plug ---------------------------------------------------------------------------
    _set(pid, step=STEPS[2], stepIndex=2, done=0, total=len(current), message='')
    settings = engine.merged_settings(pkg['settings'])
    overrides = db.many('SELECT * FROM overrides WHERE package_id=? ORDER BY created_at', (pid,))
    raw = []
    for d in current:
        ext = extract.reconcile(d['extraction'])            # also applied to readings stored before this check existed
        name = ext.get('bidder_name') or d['filename']
        raw.append({'id': bidder_id(name), 'name': name, 'cells': ext['cells'], 'extras': ext.get('extra_lines') or []})
    res = engine.level(items, raw, settings, overrides, {})
    ai_keys = sorted(engine.needs_ai(items, res['bidders']))
    ai_prices = {}
    if ai_keys:
        _set(pid, step=STEPS[3], stepIndex=3, done=0, total=len(ai_keys), message='Asking the model for unit costs')
        ctx = {'project': proj['name'], 'location': proj.get('location') or 'United States', 'package': f"{pkg['code']} {pkg['name']}"}
        by_key = {i['key']: i for i in items}
        done[0] = 0
        outs = llm.run_parallel(lambda k: assess.estimate_plug(by_key[k], ctx, settings.get('ai_web_search', True)), ai_keys, tick)
        for k, o in zip(ai_keys, outs):
            ai_prices[k] = {'error': str(o)} if isinstance(o, Exception) else o
        res = engine.level(items, raw, settings, overrides, ai_prices)
    bidders = res['bidders']
    by_doc = {bidder_id(d['extraction'].get('bidder_name') or d['filename']): d for d in current}
    for i, b in enumerate(bidders):
        b['code'] = code_for(i)
        for c in b['cells'].values():       # an AI plug far from what the other bidders charge deserves a look
            p = c.get('plug')
            if p and p['method'] == 'ai_estimate' and p['pool']:
                avg = statistics.fmean(x['value'] for x in p['pool'])
                if avg and abs(p['value'] / avg - 1) > 0.25:
                    c['flags'].append(f"AI estimate is {(p['value'] / avg - 1) * 100:+.0f}% against the other bidders' average of ${avg:,.0f}")

    # 5. assess + score --------------------------------------------------------------------------------
    _set(pid, step=STEPS[4], stepIndex=4, done=0, total=len(bidders), message='')
    support = support_text(docs)
    exts = {b['id']: by_doc[b['id']]['extraction'] for b in bidders}
    by_key = {i['key']: i for i in items}

    def do_assess(b):
        ext = exts[b['id']]
        facts = {'leveled_total': b['leveledTotal'], 'as_bid_total': b['asBid'], 'scope_priced_pct': round(b['scopePriced'] * 100),
                 'items_plugged_by_gc': [by_key[k]['name'] for k, c in b['cells'].items() if c['state'] == 'plugged'],
                 'quantity_re_extensions': b['counts']['qtyNormalized'], 'unit_conversions': b['counts']['unitNormalized'],
                 'reading_checks': ext.get('checks') or [], 'bid_date': ext.get('bid_date'), 'is_revision': ext.get('is_revision')}
        return assess.assess_bidder(b['name'], facts, extract.summarize(ext), support, pol)
    done[0] = 0
    outs = llm.run_parallel(do_assess, bidders, tick)
    assessments = {b['id']: (None if isinstance(o, Exception) else o) for b, o in zip(bidders, outs)}
    rec_id = assess.score(pol, bidders, assessments, exts)
    winner = next((b for b in bidders if b['id'] == rec_id), None)

    # 6. explanations ----------------------------------------------------------------------------------
    use_ai = settings.get('ai_text', True) and llm.available()
    _set(pid, step=STEPS[5], stepIndex=5, done=0, total=len(items) + len(bidders), message='' if use_ai else 'Templated text (AI text is off)')
    done[0] = 0
    if use_ai:
        row_out = llm.run_parallel(lambda it: explain.explain_row(it, res['rows'][it['key']], bidders, rec_id), items, tick)
        bid_out = llm.run_parallel(lambda b: explain.explain_bidder(b, winner, items, pol), bidders, tick)
    else:
        row_out = [explain.row_template(it, res['rows'][it['key']], bidders, rec_id) for it in items]
        bid_out = [explain.bidder_template(b, winner) for b in bidders]
    for it, out in zip(items, row_out):
        if isinstance(out, Exception):
            out = explain.row_template(it, res['rows'][it['key']], bidders, rec_id)
        note, cells = out
        res['rows'][it['key']]['note'] = note
        for b in bidders:
            b['cells'][it['key']]['note'] = cells[b['id']]
    for b, out in zip(bidders, bid_out):
        b['explanation'] = explain.bidder_template(b, winner) if isinstance(out, Exception) else out
    _limit_flags(items, res['rows'], bidders)

    # 7. assemble + save -------------------------------------------------------------------------------
    _set(pid, step=STEPS[6], stepIndex=6, done=0, total=1, message='')
    for b in bidders:
        d, ext = by_doc[b['id']], exts[b['id']]
        b['document'] = {'id': d['id'], 'filename': d['filename'], 'date': ext.get('bid_date'), 'uploadedAt': d['uploaded_at'], 'hasFile': bool(d.get('path'))}
        b['terms'] = {'inclusions': ext.get('inclusions') or [], 'exclusions': ext.get('exclusions') or [], 'clarifications': ext.get('clarifications') or [],
                      'warranty': ext.get('warranty') or [], 'validityDays': ext.get('validity_days'), 'addenda': ext.get('addenda_acknowledged') or [],
                      'tax': ext.get('tax'), 'taxNote': ext.get('tax_note'), 'alternates': ext.get('alternates') or [], 'redFlags': ext.get('red_flags') or []}
        b['checks'] = ext.get('checks') or []
        b['statedTotal'] = ext.get('stated_total')
        b['isRevision'] = bool(ext.get('is_revision'))
    order = sorted(bidders, key=lambda b: (not b['qualified'], b['rank'] if b['rank'] else 999, -b['score'], b['leveledTotal']))
    sections, seen = [], {}
    for it in items:
        s = it.get('section') or 'General'
        if s not in seen:
            seen[s] = {'name': s, 'keys': []}
            sections.append(seen[s])
        seen[s]['keys'].append(it['key'])
    result = {
        'package': {'id': pid, 'code': pkg['code'], 'name': pkg['name'], 'project': proj['name']},
        'leveledAt': time.time(), 'items': items, 'sections': sections, 'rows': res['rows'], 'allowances': res['allowances'],
        'bidders': order, 'declined': declined, 'superseded': superseded, 'policy': pol, 'recommendedId': rec_id,
        'settings': settings, 'aiPrices': ai_prices,
        'summary': {'received': sum(1 for d in docs if d['kind'] == 'bid'), 'leveled': len(bidders), 'qualified': sum(1 for b in bidders if b['qualified']),
                    'gcEstimate': round(sum(i.get('estimate') or 0 for i in items), 2) or None,
                    'flaggedCells': sum(1 for b in bidders for c in b['cells'].values() if c['note']['flag']),
                    'cells': len(bidders) * len(items)},
        'run': {'seconds': round(time.time() - t0, 1), 'llmCalls': llm.stats['calls'] - calls0['calls'], 'llmCached': llm.stats['cached'] - calls0['cached'],
                'llmErrors': llm.stats['errors'] - calls0['errors'], 'text': 'ai' if use_ai else 'template', 'model': llm.model_for('extract_bid'), 'stageModels': llm.stage_models.get()},
    }
    db.update('packages', pid, result=result, last_leveled_at=result['leveledAt'])
    return result
