"""AI explanations. The numbers are computed first and handed to the model as facts; the model writes the prose
and decides what is worth flagging. If a call fails, templated text built from the same facts is used instead."""
import json

from .. import llm

STR = {'type': ['string', 'null']}


def money(v):
    return f'${v:,.0f}'


def pct(d):
    return f'{abs(d) * 100:.0f}%'


def ordinal(n):
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


# ---------------------------------------------------------------- per scope item, with every bidder's cell
ROW_SCHEMA = {
    'type': 'object',
    'properties': {
        'item': {'type': 'object', 'properties': {'headline': {'type': 'string'}, 'short': {'type': 'string'}, 'full': {'type': 'string'}, 'flag': {'type': 'boolean'}},
                 'required': ['headline', 'short', 'full', 'flag']},
        'cells': {'type': 'array', 'items': {
            'type': 'object',
            'properties': {'code': {'type': 'string'}, 'short': {'type': 'string'}, 'full': {'type': 'string'}, 'flag': {'type': 'boolean'}},
            'required': ['code', 'short', 'full', 'flag']}},
    },
    'required': ['item', 'cells'],
}

ROW_PROMPT = """You are a senior construction estimator explaining a bid leveling to a colleague.
Below are the computed facts for ONE scope item across every bidder. Write the analysis. Use only these facts;
every number you mention must appear in them. Plain, direct sentences. No hedging, no filler.

For the scope item (`item`):
- headline: at most 40 characters, e.g. "Contested · GC est. 25% under · 1 plug" or "Tight · 2 plugs".
- short: one or two sentences (at most 160 characters) on how the field priced this item.
- full: 3 to 5 sentences: spread, who is lowest and highest, how the GC estimate compares, what the qualified
  bidders and the recommended bidder did, any unit or quantity normalizations, any plugs, and what to check.
- flag: true only if an estimator should look at this item before award (wide spread, many bidders left it
  out, the GC estimate looks wrong, bidders used different units or quantities).

For EACH bidder (`cells`, one entry per bidder code, same order as given):
- short: at most 160 characters: where this price stands among all the bids for the item (rank, distance from the
  reference), and what was done to it (unit converted, quantity re-extended, plugged, included elsewhere).
- full: 2 to 4 sentences, at most 70 words: the same in more detail. Say the as-bid figure when it differs from the
  leveled one, explain the conversion or the quantity difference in words, say which plug method was used and
  why the item needed a plug, and end with "To check: ..." when something should be confirmed with the bidder.
  If the bidder did not qualify, say the value is context only.
- flag: true for roughly one cell in ten: an isolated low or high price, a large quantity difference, a material
  plug, a conversion that changes the picture, a low-confidence reading. Most cells are false.

FACTS:
{facts}"""


def row_facts(item, row, bidders, recommended_id, ref_name='median'):
    cells = []
    for b in bidders:
        c = b['cells'][item['key']]
        f = {'code': b['code'], 'bidder': b['name'], 'qualified': b['qualified'], 'recommended': b['id'] == recommended_id, 'state': c['state']}
        ab = c['asBid']
        if ab.get('amount') is not None:
            f['as_bid'] = {k: ab[k] for k in ('qty', 'unit', 'unitPrice', 'amount') if ab.get(k) is not None}
        if c.get('unitNorm') and c['unitNorm']['applied']:
            u = c['unitNorm']
            f['unit_normalized'] = f"{u['from']} to {u['to']}: {u['explanation']} (source: {u['source']})"
        if c.get('qtyNorm'):
            q = c['qtyNorm']
            f['quantity'] = {'bid_qty_in_gc_unit': q['bidQty'], 'gc_qty': q['gcQty'], 'variance_pct': q['variancePct'], 're_extended': q['applied'], 'adjustment': q['adjustment']}
        if c.get('plug'):
            p = c['plug']
            f['plug'] = {'reason': p['reason'], 'method': p['label'], 'value': p['value'], 'formula': p['formula'], 'share_of_bidder_total_pct': round(p['value'] / b['leveledTotal'] * 100, 1) if b['leveledTotal'] else None}
        if c['value'] is not None:
            f['leveled_value'] = c['value']
        if c.get('dev') is not None:
            f['vs_reference_pct'] = round(c['dev'] * 100, 1)
        if c.get('rank'):
            f['rank_low_to_high'] = f"{c['rank']} of {c['of']}"
        if c.get('confidence') is not None and c['confidence'] < 0.7:
            f['reading_confidence'] = c['confidence']
        if c.get('flags'):
            f['checks'] = c['flags']
        if c.get('override'):
            f['estimator_override'] = c['override']['action']
        cells.append(f)
    return {'item': item['name'], 'unit': item.get('unit'), 'gc_quantity': item.get('qty'), 'gc_estimate': item.get('estimate'),
            'reference': {'kind': row['refKind'], 'value': row['ref']},
            'priced_by': row['n'], 'bidders_total': len(bidders), 'plugged': row['plugged'], 'included_elsewhere': row['included'],
            'min': row['min'], 'lower_quartile': row['q1'], 'median': row['med'], 'upper_quartile': row['q3'], 'max': row['max'],
            'unit_normalized_count': row['unitNormalized'], 'quantity_normalized_count': row['qtyNormalized'], 'cells': cells}


def row_template(item, row, bidders, recommended_id):
    """Templated analysis from the facts: used when the model is unavailable, and as the instant first version."""
    n, tot = row['n'], len(bidders)
    iqr = (row['q3'] - row['q1']) / row['med'] if n >= 3 and row['med'] else None
    level = None if iqr is None else 'Contested' if iqr > 0.3 else 'Moderate' if iqr > 0.14 else 'Tight'
    head = 'No priced bids; all plugs' if not n else 'Too few bids to judge' if level is None else level
    if n >= 3 and item.get('estimate') and row['med']:
        d = item['estimate'] / row['med'] - 1
        if abs(d) > 0.15:
            head += f" · GC est. {pct(d)} {'under' if d < 0 else 'over'}"
    if row['plugged']:
        head += f" · {row['plugged']} plug{'s' if row['plugged'] != 1 else ''}"
    short = ('No bidder priced this item; every value is a plug.' if not n else
             f"Only {n} priced bid{'s' if n != 1 else ''}, too few to judge the spread." if level is None else
             f"{level}: middle half of bids from {money(row['q1'])} to {money(row['q3'])}." + (f" {row['plugged']} did not price it." if row['plugged'] else ''))
    full = [f"{n} of {tot} bidders priced this item" + (f"; {row['plugged']} plugged by the GC" if row['plugged'] else '') + '.']
    if n >= 2:
        full.append(f"Prices run from {money(row['min'])} to {money(row['max'])}" + (f", median {money(row['med'])}" if n >= 3 else '') + '.')
    if row['unitNormalized'] or row['qtyNormalized']:
        full.append(f"{row['unitNormalized']} bid(s) were converted to the GC unit and {row['qtyNormalized']} re-extended to the GC quantity.")
    if level == 'Contested':
        full.append('To check: whether bidders priced the same scope and quantity.')
    heavy = tot >= 3 and row['plugged'] / tot >= 0.2
    note = {'headline': head[:44], 'short': short, 'full': ' '.join(full), 'flag': level == 'Contested' or heavy, 'source': 'template'}
    cells = {}
    priced = sorted((b['cells'][item['key']]['value'], b['id']) for b in bidders if b['cells'][item['key']]['state'] == 'priced')
    for b in bidders:
        c = b['cells'][item['key']]
        flag = False
        if c['state'] == 'included':
            s = 'Bidder states this is covered in another line, so there is no separate value.'
        elif c['state'] == 'plugged':
            share = c['value'] / b['leveledTotal'] if b['leveledTotal'] else 0
            s = f"{c['plug']['reason']}. Plugged at {money(c['value'])} ({c['plug']['label']}), {max(1, round(share * 100))}% of this bidder's leveled total."
            flag = share >= 0.05
        else:
            rel = (f"In line with the {row['refKind']}" if c.get('dev') is not None and abs(c['dev']) <= 0.05 else
                   f"{pct(c['dev'])} {'below' if c['dev'] < 0 else 'above'} the {row['refKind']}" if c.get('dev') is not None else 'Priced')
            pos = '' if not c.get('rank') or c['of'] < 2 else f"; {'the lowest' if c['rank'] == 1 else 'the highest' if c['rank'] == c['of'] else ordinal(c['rank']) + ' lowest'} of {c['of']} priced bids"
            pre = ''
            if c.get('unitNorm') and c['unitNorm']['applied']:
                pre += f"Converted {c['unitNorm']['from']} to {c['unitNorm']['to']}. "
            if c.get('qtyNorm') and c['qtyNorm']['applied']:
                pre += f"Re-extended to the GC quantity ({'+' if c['adjustment'] >= 0 else '-'}{money(abs(c['adjustment']))}). "
                flag = abs(c['qtyNorm']['variancePct']) >= 15
            s = pre + rel + pos + '.'
            k = next((i for i, p in enumerate(priced) if p[1] == b['id']), None)
            if k is not None and len(priced) >= 3:
                if k == 0 and (priced[1][0] - c['value']) / priced[1][0] > 0.15:
                    flag = True
                if k == len(priced) - 1 and (c['value'] - priced[-2][0]) / priced[-2][0] > 0.15:
                    flag = True
        f = s + ('' if b['qualified'] else ' This bidder did not qualify, so the value is context only.')
        cells[b['id']] = {'short': s[:200], 'full': f, 'flag': bool(flag or any(not x.startswith('Lump sum') for x in c.get('flags') or [])), 'source': 'template'}
    return note, cells


def explain_row(item, row, bidders, recommended_id):
    """Returns (item_note, {bidder_id: cell_note}). Falls back to the template on any failure."""
    tnote, tcells = row_template(item, row, bidders, recommended_id)
    try:
        out = llm.generate_json(ROW_PROMPT.format(facts=json.dumps(row_facts(item, row, bidders, recommended_id))), ROW_SCHEMA, kind='explain_row')
    except llm.LLMError:
        return tnote, tcells
    it = out.get('item') or {}
    mixed = row['unitNormalized'] + row['qtyNormalized'] >= max(2, len(bidders) // 3)
    note = {'headline': (it.get('headline') or tnote['headline'])[:60], 'short': it.get('short') or tnote['short'],
            'full': it.get('full') or tnote['full'], 'flag': bool(it.get('flag')) and (tnote['flag'] or mixed), 'source': 'ai'}
    by_code = {c.get('code'): c for c in out.get('cells') or []}
    cells = {}
    for b in bidders:
        c = by_code.get(b['code'])
        hard = any(not f.startswith('Lump sum') for f in b['cells'][item['key']].get('flags') or [])   # arithmetic and conversion checks always raise the flag
        cell = b['cells'][item['key']]
        material = (                                        # is there something in the numbers that backs the model's flag?
            (cell['state'] == 'plugged' and b['leveledTotal'] and cell['value'] / b['leveledTotal'] >= 0.03)
            or (cell['state'] == 'priced' and cell.get('dev') is not None and abs(cell['dev']) >= 0.25)
            or (cell.get('qtyNorm') and cell['qtyNorm']['applied'] and abs(cell['qtyNorm']['variancePct']) >= 10)
            or (cell.get('unitNorm') and cell['unitNorm']['applied'] and cell['unitNorm']['source'] == 'llm')
            or (cell.get('confidence') is not None and cell['confidence'] < 0.7) or tcells[b['id']]['flag'])
        cells[b['id']] = ({'short': c['short'], 'full': c['full'], 'flag': (bool(c.get('flag')) and bool(material)) or hard, 'source': 'ai'} if c and c.get('short') else tcells[b['id']])
    return note, cells


# ---------------------------------------------------------------- per subcontractor: why it won or lost
BIDDER_SCHEMA = {
    'type': 'object',
    'properties': {
        'headline': {'type': 'string'}, 'summary': {'type': 'string'},
        'strengths': {'type': 'array', 'items': {'type': 'string'}},
        'weaknesses': {'type': 'array', 'items': {'type': 'string'}},
        'deciding_factors': {'type': 'array', 'items': {'type': 'string'}},
        'what_would_change': {'type': 'string'},
    },
    'required': ['headline', 'summary', 'strengths', 'weaknesses', 'deciding_factors', 'what_would_change'],
}

BIDDER_PROMPT = """You are a senior construction estimator writing the award explanation for one subcontractor.
Use only the facts below; every number you mention must appear in them. Plain, direct sentences.

Outcome for this bidder: {outcome}

Write:
- headline: at most 80 characters, the one-line reason for the outcome.
- summary: 3 to 4 sentences. For the recommended bidder: why it wins under the award rule and the weighted criteria. For the
  others: why it did not win, compared with the recommended bidder, criterion by criterion where it matters,
  and which scope items drive the price difference. If it did not qualify, lead with the rule it failed.
- strengths: up to 4 short bullets.
- weaknesses: up to 4 short bullets (plugs, exclusions, quantity differences, weak terms, failed rules).
- deciding_factors: up to 3 bullets naming the criteria or scope items that decided the outcome, with the numbers.
- what_would_change: one sentence on what would have to be different for the outcome to change.

FACTS:
{facts}"""


def bidder_facts(b, winner, items, policy):
    drivers = []
    if winner and winner['id'] != b['id']:
        for it in items:
            mine, theirs = b['cells'][it['key']], winner['cells'][it['key']]
            if mine['value'] is not None and theirs['value'] is not None:
                drivers.append({'item': it['name'], 'this_bidder': mine['value'], 'recommended_bidder': theirs['value'],
                                'difference': round(mine['value'] - theirs['value'], 2), 'this_state': mine['state'], 'recommended_state': theirs['state']})
        drivers = sorted(drivers, key=lambda d: -abs(d['difference']))[:6]
    plugs = [{'item': next(i['name'] for i in items if i['key'] == k), 'value': c['value'], 'method': c['plug']['label'], 'reason': c['plug']['reason']}
             for k, c in b['cells'].items() if c['state'] == 'plugged']
    adj = [{'item': next(i['name'] for i in items if i['key'] == k), 'variance_pct': c['qtyNorm']['variancePct'], 'adjustment': c['adjustment']}
           for k, c in b['cells'].items() if c.get('qtyNorm') and c['qtyNorm']['applied']]
    f = {'award_rule': (policy.get('award_rule') or {}).get('summary'), 'why_recommended_bidder_was_chosen': (winner or {}).get('awardNote'),
         'bidder': b['name'], 'qualified': b['qualified'], 'rank': b['rank'], 'weighted_score': b['score'],
         'leveled_total': b['leveledTotal'], 'as_bid_total': b['asBid'], 'quantity_adjustments': b['quantityAdjustments'], 'plugs_total': b['plugs'],
         'scope_priced_pct': round(b['scopePriced'] * 100), 'pct_above_lowest_total': b['pctAboveLow'],
         'criteria': [{'ordinal': r['ordinal'], 'criterion': r['name'], 'weight': r['weight'], 'points': r['points'], 'weighted': r['weighted'], 'rating': r['label'], 'why': r['justification']} for r in b['ratings']],
         'rules': [{'rule': g['name'], 'result': g['result'], 'reason': g['reason'], 'severity': g['severity']} for g in b['gates']],
         'plugs': plugs, 'quantity_re_extensions': adj}
    if winner and winner['id'] != b['id']:
        f['recommended_bidder'] = {'name': winner['name'], 'weighted_score': winner['score'], 'leveled_total': winner['leveledTotal'],
                                   'criteria': [{'criterion': r['name'], 'points': r['points'], 'weighted': r['weighted'], 'rating': r['label']} for r in winner['ratings']]}
        f['largest_item_differences_vs_recommended'] = drivers
    return f


def bidder_template(b, winner):
    if b['band'] == 'recommended':
        head, summ = 'Highest weighted score among qualified bidders', f"{b['name']} scores {b['score']:.1f} with a leveled total of {money(b['leveledTotal'])}."
    elif not b['qualified']:
        head, summ = 'Did not qualify under the award policy', ' '.join(b['reasons'])
    else:
        gap = f" against {winner['score']:.1f} for {winner['name']}" if winner else ''
        head, summ = f"Ranked {ordinal(b['rank'])} on weighted score", f"{b['name']} scores {b['score']:.1f}{gap}, with a leveled total of {money(b['leveledTotal'])}."
    best = sorted(b['ratings'], key=lambda r: -r['points'])[:2]
    worst = sorted(b['ratings'], key=lambda r: r['points'])[:2]
    return {'headline': head, 'summary': summ, 'strengths': [f"{r['name']}: {r['label']}" for r in best],
            'weaknesses': [f"{r['name']}: {r['label']}" for r in worst if r['points'] < 100] + b['reasons'][:2],
            'deciding_factors': [f"{r['name']} ({r['weight']:g}%): {r['points']:.0f} points" for r in sorted(b['ratings'], key=lambda r: -r['weight'])[:2]],
            'what_would_change': '', 'source': 'template'}


def explain_bidder(b, winner, items, policy):
    outcome = ('RECOMMENDED (rank 1)' if b['band'] == 'recommended' else
               'DID NOT QUALIFY: ' + '; '.join(b['reasons']) if not b['qualified'] else f"NOT RECOMMENDED (rank {b['rank']})")
    try:
        out = llm.generate_json(BIDDER_PROMPT.format(outcome=outcome, facts=json.dumps(bidder_facts(b, winner, items, policy))), BIDDER_SCHEMA, kind='explain_bidder')
        out['source'] = 'ai'
        return out
    except llm.LLMError:
        return bidder_template(b, winner)
