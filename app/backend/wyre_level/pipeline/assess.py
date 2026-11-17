"""AI plug estimates, AI assessment of each bidder against the ordinals, and the deterministic scoring that follows."""
import json

from .. import llm

NUM = {'type': ['number', 'null']}
STR = {'type': ['string', 'null']}

# ---------------------------------------------------------------- AI plug estimate
PLUG_PROMPT = """You are a construction cost estimator. Estimate what a subcontractor would charge a general contractor
(installed: labor, material, equipment, overhead and profit; excluding sales tax) for this scope item.

Project: {project}, {location}. Bid package: {package}.
Scope item: {name}
GC unit of measure: {unit}{qty}{depth}
{hint}
Use current pricing for this region. If your sources price the work in a different unit (per square, per square
yard, per cubic yard, per roll, per linear metre, per hour...), convert to the GC unit and say how in `conversion_note`.

Reply with ONLY a JSON object, no prose:
{{"unit_price": number or null (USD per {unit}; null for a lump sum item),
  "lump_sum": number or null (USD for the whole item; only for lump sum items),
  "low": number, "high": number (the plausible range, same basis as the estimate),
  "confidence": "high" | "medium" | "low",
  "basis": "one or two sentences on how the figure was built",
  "conversion_note": "how market units were converted to the GC unit, or 'none needed'"}}
Set confidence to "low" if you cannot ground the figure in anything specific."""


def estimate_plug(item, ctx, web_search=True):
    """Returns {'value', 'unit_price', 'low', 'high', 'confidence', 'basis', 'conversion_note', 'sources', 'grounded'} or {'error'}."""
    ls = not item.get('qty')
    hint = (f"For reference only, the GC's own budget figure for this item is ${item['estimate']:,.0f}. "
            'Form your own estimate; do not simply repeat it.') if item.get('estimate') else ''
    prompt = PLUG_PROMPT.format(project=ctx.get('project', 'Commercial building'), location=ctx.get('location', 'United States'),
                                package=ctx.get('package', ''), name=item['name'], unit=item.get('unit') or 'LS',
                                qty='' if ls else f"; GC quantity: {item['qty']:,.0f} {item['unit']}",
                                depth=f"; specified depth {item['depth']:g} in." if item.get('depth') else '', hint=hint)
    data, sources, grounded = None, [], False
    if web_search:
        try:
            data, sources = llm.generate_grounded_json(prompt, kind='ai_plug_grounded')
            grounded = True
        except llm.LLMError:
            data = None
    if data is None:
        schema = {'type': 'object', 'properties': {'unit_price': NUM, 'lump_sum': NUM, 'low': NUM, 'high': NUM,
                                                   'confidence': {'type': 'string', 'enum': ['high', 'medium', 'low']},
                                                   'basis': {'type': 'string'}, 'conversion_note': {'type': 'string'}},
                  'required': ['confidence', 'basis']}
        try:
            data = llm.generate_json(prompt, schema, kind='ai_plug')
        except llm.LLMError as e:
            return {'error': str(e)}
    up, lump = data.get('unit_price'), data.get('lump_sum')
    if ls:
        value = lump if lump is not None else up
        up = None
    else:
        value = up * item['qty'] if up is not None else lump
        if up is None and lump is not None:
            up = lump / item['qty']
    if value is None:
        return {'error': 'no figure returned'}
    scale = (item['qty'] if (not ls and data.get('unit_price') is not None) else 1)
    return {'value': round(value, 2), 'unit_price': round(up, 4) if up is not None else None,
            'low': round(data['low'] * scale, 2) if data.get('low') is not None else None,
            'high': round(data['high'] * scale, 2) if data.get('high') is not None else None,
            'confidence': data.get('confidence', 'low'), 'basis': data.get('basis'), 'conversion_note': data.get('conversion_note'),
            'sources': sources[:6], 'grounded': grounded}


# ---------------------------------------------------------------- AI assessment of one bidder
ASSESS_SCHEMA = {
    'type': 'object',
    'properties': {
        'gates': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'id': {'type': 'string'}, 'result': {'type': 'string', 'enum': ['pass', 'fail', 'unknown']},
                           'reason': {'type': 'string'}, 'evidence': STR},
            'required': ['id', 'result', 'reason']}},
        'ratings': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'criterion_id': {'type': 'string'}, 'level': {'type': 'integer'}, 'justification': {'type': 'string'}, 'evidence': STR},
            'required': ['criterion_id', 'level', 'justification']}},
    },
    'required': ['gates', 'ratings'],
}

ASSESS_PROMPT = """You are evaluating one subcontractor's bid for a general contractor, against the GC's award criteria.
Judge only from the material below. If the material does not let you decide a rule, answer "unknown" and say what
is missing; do not guess. Quote or point to the evidence you relied on.

PASS/FAIL RULES TO DECIDE (one result for each id):
{gates}

CRITERIA TO RATE (pick one `level` from each scale):
{criteria}

BIDDER: {name}
Leveling facts: {facts}

Terms read from the bid:
{terms}

SUPPORTING DATA (prequalification roster, clarification log, project brief; may not mention this bidder):
{support}"""


def assess_bidder(name, facts, terms, support, policy):
    judge_gates = [g for g in policy['gates'] if g['check'] == 'judgement']
    qual = [c for c in policy['criteria'] if c['kind'] == 'qualitative']
    if not judge_gates and not qual:
        return {'gates': [], 'ratings': []}
    gates = '\n'.join(f"- {g['id']}: {g['name']}. {g['rule']}" for g in judge_gates) or '(none)'
    crit = '\n'.join(f"- {c['id']}: {c['name']}. {c['description']}\n" + '\n'.join(
        f"    level {s['level']} = {s['label']}: {s['definition']}" for s in c['scale']) for c in qual) or '(none)'
    prompt = ASSESS_PROMPT.format(gates=gates, criteria=crit, name=name, facts=json.dumps(facts), terms=terms, support=support[:24000] or '(none provided)')
    return llm.generate_json(prompt, ASSESS_SCHEMA, kind='assess')


# ---------------------------------------------------------------- deterministic scoring
def score(policy, bidders, assessments, terms):
    """bidders: leveled bidders (engine output). assessments: {bidder_id: assess result or None}. terms: {bidder_id: extraction}.
    Adds gates, qualified, reasons, ratings, score, rank and band to each bidder; returns the recommended bidder id."""
    for b in bidders:
        a = assessments.get(b['id']) or {'gates': [], 'ratings': []}
        judged = {g['id']: g for g in a.get('gates') or []}
        gates = []
        for g in policy['gates']:
            res, reason, ev = 'unknown', 'Not assessed', None
            if g['check'] == 'scope_priced_min_pct' and g.get('threshold') is not None:
                pct = b['scopePriced'] * 100
                res = 'pass' if pct + 1e-9 >= g['threshold'] else 'fail'
                reason = f"Priced {pct:.0f}% of the scope by value; the policy requires {g['threshold']:g}%."
            elif g['check'] == 'bid_validity_min_days' and g.get('threshold') is not None:
                v = (terms.get(b['id']) or {}).get('validity_days')
                if v is None:
                    res, reason = 'unknown', 'The bid does not state how long the price is valid.'
                else:
                    res = 'pass' if v >= g['threshold'] else 'fail'
                    reason = f"Bid valid for {v:g} days; the policy asks for {g['threshold']:g}."
            elif g['id'] in judged:
                j = judged[g['id']]
                res, reason, ev = j['result'], j['reason'], j.get('evidence')
            gates.append({'id': g['id'], 'name': g['name'], 'rule': g['rule'], 'severity': g['severity'], 'result': res, 'reason': reason, 'evidence': ev})
        b['gates'] = gates
        b['reasons'] = [f"{g['name']}: {g['reason']}" for g in gates if g['result'] == 'fail' and g['severity'] == 'disqualify']
        b['warnings'] = [f"{g['name']}: {g['reason']}" for g in gates if (g['result'] == 'fail' and g['severity'] == 'flag') or g['result'] == 'unknown']
        b['qualified'] = not b['reasons']

    field = [b for b in bidders if b['qualified']] or bidders
    low = min((b['leveledTotal'] for b in field if b['leveledTotal'] > 0), default=None)
    for b in bidders:
        a = assessments.get(b['id']) or {'ratings': []}
        rated = {r['criterion_id']: r for r in a.get('ratings') or []}
        ratings, total = [], 0.0
        for c in policy['criteria']:
            scale = c.get('scale') or []
            if c['kind'] == 'price':
                pts = min(100.0, 100.0 * low / b['leveledTotal']) if low and b['leveledTotal'] > 0 else 0.0
                label = 'Lowest' if low and abs(b['leveledTotal'] - low) < 0.5 else f"{(b['leveledTotal'] / low - 1) * 100:+.1f}% vs lowest qualified" if low else 'n/a'
                why = f"Leveled total ${b['leveledTotal']:,.0f}; lowest qualified total ${low:,.0f}." if low else 'No totals to compare.'
            elif c['kind'] == 'scope_completeness':
                pts = b['scopePriced'] * 100
                label = f"{pts:.0f}% priced"
                why = f"The bidder priced {pts:.0f}% of the scope by value; {b['counts']['plugged']} item(s) were plugged by the GC."
            else:
                r = rated.get(c['id'])
                lvl = next((s for s in scale if r and s['level'] == r['level']), None)
                if lvl:
                    pts, label, why = float(lvl['points']), lvl['label'], r['justification']
                else:
                    mid = scale[len(scale) // 2] if scale else {'points': 50, 'label': 'Not rated'}
                    pts, label, why = float(mid['points']), 'Not rated', 'No assessment available; scored at the middle of the scale.'
            w = round(c['weight'] * pts / 100, 2)
            total += w
            ratings.append({'criterionId': c['id'], 'name': c['name'], 'ordinal': c['ordinal'], 'weight': c['weight'], 'kind': c['kind'],
                            'points': round(pts, 1), 'weighted': w, 'label': label, 'justification': why,
                            'evidence': (rated.get(c['id']) or {}).get('evidence') if c['kind'] == 'qualitative' else None})
        b['ratings'] = ratings
        b['score'] = round(total, 1)

    ranked = sorted((b for b in bidders if b['qualified']), key=lambda b: (-b['score'], b['leveledTotal']))
    rule = policy.get('award_rule') or {'basis': 'highest_score'}
    for b in bidders:
        b['awardNote'] = None
    if rule.get('basis') == 'lowest_price' and ranked:
        # the policy's own rule: lowest leveled total among qualified bidders; another bidder only within the best-value window
        by_price = sorted(ranked, key=lambda b: b['leveledTotal'])
        low = by_price[0]['leveledTotal']
        win = (rule.get('best_value_window_pct') or 0) / 100
        pool = [b for b in by_price if b['leveledTotal'] <= low * (1 + win) + 0.01]
        top = max(pool, key=lambda b: (b['score'], -b['leveledTotal']))
        top['awardNote'] = ('Lowest leveled total among qualified bidders' if top is by_price[0] else
                            f"Within {rule['best_value_window_pct']:g}% of the lowest qualified total, with the highest weighted score in that range")
        ranked = [top] + [b for b in by_price if b is not top]
    elif ranked:
        ranked[0]['awardNote'] = 'Highest weighted score among qualified bidders'
    for i, b in enumerate(ranked, 1):
        b['rank'] = i
        b['band'] = 'recommended' if i == 1 else 'alternative' if i <= 3 else 'other'
    for b in bidders:
        if not b['qualified']:
            b['rank'], b['band'] = None, 'not_qualified'
    lows = [b['leveledTotal'] for b in bidders if b['leveledTotal'] > 0]
    lo_all = min(lows) if lows else None
    for b in bidders:
        b['isLow'] = bool(lo_all) and abs(b['leveledTotal'] - lo_all) < 0.5
        b['pctAboveLow'] = round((b['leveledTotal'] / lo_all - 1) * 100, 1) if lo_all and b['leveledTotal'] > 0 else None
    return ranked[0]['id'] if ranked else None
