"""Deterministic leveling engine: unit conversion, quantity normalization, plugs, totals, row statistics.

Ported from tools/gen_samples/plugging.py (the reference engine behind the sample answer keys) and extended
with LLM-supplied conversion factors, AI plug estimates and per-cell overrides. No model calls happen here.
"""
import re
import statistics

AREA = {'SF': 1.0, 'SQ': 100.0, 'SY': 9.0, 'M2': 10.7639, 'ROLL': 10.0}
LENGTH = {'LF': 1.0, 'FT': 1.0, 'PANEL': 8.0, 'M': 3.28084}
VOLUME = {'CY': 1.0, 'M3': 1.30795}
ALIASES = {
    'SQFT': 'SF', 'SQ FT': 'SF', 'SQUARE FEET': 'SF', 'SQUARE FOOT': 'SF', 'FT2': 'SF', 'S.F.': 'SF', 'SF.': 'SF',
    'SQS': 'SQ', 'SQUARE': 'SQ', 'SQUARES': 'SQ', 'ROOFING SQUARES': 'SQ',
    'SQYD': 'SY', 'SQ YD': 'SY', 'SQUARE YARD': 'SY', 'SQUARE YARDS': 'SY', 'YD2': 'SY', 'S.Y.': 'SY',
    'M²': 'M2', 'SQM': 'M2', 'SQ M': 'M2', 'SM': 'M2', 'SQUARE METRE': 'M2', 'SQUARE METRES': 'M2', 'SQUARE METER': 'M2', 'SQUARE METERS': 'M2',
    'ROLLS': 'ROLL', 'PANELS': 'PANEL', 'LIN FT': 'LF', 'LINEAR FEET': 'LF', 'LINEAR FOOT': 'LF', 'FEET': 'FT', 'FOOT': 'FT', 'L.F.': 'LF',
    'CUBIC METRE': 'M3', 'CUBIC METRES': 'M3', 'CUBIC METER': 'M3', 'CUBIC METERS': 'M3', 'M³': 'M3', 'CU M': 'M3', 'CUM': 'M3',
    'CUBIC YARD': 'CY', 'CUBIC YARDS': 'CY', 'CU YD': 'CY', 'YD3': 'CY', 'C.Y.': 'CY', 'YARDS': 'CY',
    'EACH': 'EA', 'EA.': 'EA', 'NO': 'EA', 'NO.': 'EA', 'PCS': 'EA', 'PC': 'EA', 'UNIT': 'EA', 'UNITS': 'EA', 'TREES': 'EA', 'TREE': 'EA',
    'LUMP SUM': 'LS', 'L.S.': 'LS', 'LUMP': 'LS', 'LOT': 'LS', 'JOB': 'LS', 'YEAR': 'YR', 'YEARS': 'YR',
}
STAT = {'min': min, 'max': max, 'average': statistics.fmean, 'median': statistics.median}
VALUE_METHODS = {'min_of_bidders': 'min', 'max_of_bidders': 'max', 'average_of_bidders': 'average', 'median_of_bidders': 'median'}
METHOD_LABEL = {
    'gc_estimate': 'GC estimate', 'min_of_bidders': 'Lowest of other bids', 'max_of_bidders': 'Highest of other bids',
    'average_of_bidders': 'Average of other bids', 'median_of_bidders': 'Median of other bids',
    'unit_rate_x_gc_qty': 'Unit rate x GC quantity', 'fixed_allowance': 'Fixed allowance', 'ai_estimate': 'AI estimate',
    'manual': 'Manual value',
}
DEFAULT_SETTINGS = {
    'threshold_pct': 5.0,
    'ai_auto': False,
    'ai_web_search': True,
    'default': {'method': 'average_of_bidders', 'fallback': ['gc_estimate'], 'min_pool': 2, 'outlier_trim_pct': 50, 'outlier_trim_min_pool': 3},
    'items': {},
    'allowances': [],
}


def r2(x):
    return round(x + 1e-9, 2)


_ALIASES = {re.sub(r'\s+', ' ', k.replace('.', '')).strip(): v for k, v in ALIASES.items()}


def norm_unit(u):
    if not u:
        return None
    s = re.sub(r'\s+', ' ', str(u).upper().replace('.', '')).strip()
    return _ALIASES.get(s, s)


def table_factor(unit, gc_unit, depth=None, gc_depth=None):
    """GC units per one bid unit from the standard table, with an explanation; None when the table has no answer."""
    unit, gc_unit = norm_unit(unit), norm_unit(gc_unit)
    if not unit or not gc_unit:
        return None
    d = depth or gc_depth
    if unit in AREA and gc_unit == 'SF':
        f, why = AREA[unit], (f'1 {unit} = {AREA[unit]:g} SF' if unit != 'SF' else 'same unit')
        if gc_depth and d and d != gc_depth:
            f, why = f * d / gc_depth, f'{why}; quoted at {d:g} in. depth against {gc_depth:g} in. specified (x {d:g}/{gc_depth:g})'
        return f, why
    if unit == 'CY' and gc_unit == 'SF':
        return (324.0 / d, f'1 CY covers 324 / {d:g} in. = {324.0 / d:.1f} SF') if d else None
    if unit in AREA and gc_unit == 'CY':
        return (AREA[unit] * d / 324.0, f'1 {unit} at {d:g} in. depth = {AREA[unit] * d / 324.0:.4f} CY') if d else None
    if unit in VOLUME and gc_unit in VOLUME:
        f = VOLUME[unit] / VOLUME[gc_unit]
        return f, (f'1 {unit} = {f:g} {gc_unit}' if unit != gc_unit else 'same unit')
    if unit in LENGTH and gc_unit == 'LF':
        return LENGTH[unit], (f'1 {unit} = {LENGTH[unit]:g} LF' if LENGTH[unit] != 1 else 'same length unit')
    if unit == gc_unit:
        return 1.0, 'same unit'
    return None


def cls(dev):
    """Seven deviation classes, the same thresholds as the visualization spec."""
    return 0 if dev <= -0.30 else 1 if dev <= -0.15 else 2 if dev < -0.05 else 3 if dev <= 0.05 else 4 if dev < 0.15 else 5 if dev < 0.30 else 6


def quant(sorted_vals, p):
    if not sorted_vals:
        return None
    x = (len(sorted_vals) - 1) * p
    lo, hi = int(x), min(int(x) + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (x - lo)


def merged_settings(settings):
    s = {**DEFAULT_SETTINGS, **(settings or {})}
    s['default'] = {**DEFAULT_SETTINGS['default'], **((settings or {}).get('default') or {})}
    s['items'] = dict(s.get('items') or {})
    s['allowances'] = list(s.get('allowances') or [])
    return s


# ---------------------------------------------------------------- one cell: as bid -> unit -> quantity
def normalize_cell(item, raw, override, threshold_pct):
    """raw: the extracted cell for this bidder and item (or None). Returns the cell with its normalization trail."""
    raw = raw or {'status': 'not_mentioned'}
    status = raw.get('status') or 'not_mentioned'
    cell = {
        'item': item['key'], 'state': 'gap', 'status': status,
        'asBid': {'qty': raw.get('quantity'), 'unit': raw.get('unit'), 'unitPrice': raw.get('unit_price'), 'amount': raw.get('amount'),
                  'description': raw.get('bid_description'), 'depthIn': raw.get('depth_in'), 'unitNote': raw.get('unit_note')},
        'unitNorm': None, 'qtyNorm': None, 'plug': None, 'value': None, 'adjustment': 0.0, 'flags': [],
        'confidence': raw.get('confidence'), 'snippet': raw.get('source_snippet'), 'extractNote': raw.get('note'),
        'override': None, 'gapReason': None,
    }
    if override:
        act, pl = override['action'], override.get('payload') or {}
        cell['override'] = {'action': act, **pl}
        if act == 'manual_value':
            cell.update(state='priced', value=r2(float(pl['value'])))
            cell['adjustment'] = r2(cell['value'] - (raw.get('amount') or 0)) if status == 'priced' and raw.get('amount') else 0.0
            return cell
        if act == 'include':
            cell.update(state='included')
            return cell
        if act in ('exclude', 'plug'):
            cell.update(state='gap', gapReason='Marked as not priced by the estimator' if act == 'exclude' else 'Plug requested by the estimator')
            return cell
    if status == 'included':
        cell['state'] = 'included'
        return cell
    if status != 'priced':
        cell['gapReason'] = 'Excluded by the bidder' if status == 'excluded' else 'Not priced by the bidder'
        return cell
    qty, unit, up, amount = raw.get('quantity'), raw.get('unit'), raw.get('unit_price'), raw.get('amount')
    if amount is None and qty and up is not None:
        amount = r2(qty * up)
        cell['flags'].append('Amount computed from quantity x unit price; the bid shows no extension')
    if amount is None:
        cell.update(state='gap', gapReason='No amount could be read for this item')
        return cell
    amount = r2(float(amount))
    cell['asBid']['amount'] = amount
    cell.update(state='priced', value=amount)
    if qty and up is not None and abs(qty * up - amount) > max(1.0, 0.0005 * abs(amount)):
        cell['flags'].append(f'Arithmetic: {qty:g} x ${up:,.2f} = ${qty * up:,.2f}, but the bid shows ${amount:,.2f}')
    gc_unit, gc_qty = norm_unit(item.get('unit')), item.get('qty')
    if not qty or not unit:
        if gc_qty:
            cell['flags'].append('Lump sum with no quantity: cannot be checked against the GC takeoff')
        return cell
    bu = norm_unit(unit)
    depth, gc_depth = raw.get('depth_in'), item.get('depth')
    tf = table_factor(bu, gc_unit, depth, gc_depth)
    llm_f = raw.get('gc_units_per_bid_unit')
    factor = source = why = None
    if tf:
        factor, why, source = tf[0], tf[1], 'table'
        if llm_f and abs(llm_f / factor - 1) > 0.02:
            cell['flags'].append(f'Unit conversion: the document reading suggests x{llm_f:g}, the standard table gives x{factor:g}; table used')
    elif llm_f:
        factor, why, source = float(llm_f), raw.get('conversion_explanation') or f'1 {unit} = {llm_f:g} {item.get("unit")}', 'llm'
    if factor is None:
        cell['flags'].append(f'Unit {unit} could not be converted to {item.get("unit")}; quantity not checked')
        return cell
    applied = abs(factor - 1) > 1e-9 or (bu != gc_unit)
    qty_gc = qty * factor
    cell['unitNorm'] = {'applied': applied, 'from': unit, 'to': item.get('unit'), 'factor': round(factor, 6), 'explanation': why, 'source': source,
                        'qtyInGcUnit': round(qty_gc, 2), 'rateInGcUnit': round(amount / qty_gc, 4) if qty_gc else None}
    if gc_qty and qty_gc:
        var = (qty_gc - gc_qty) / gc_qty * 100
        qn = {'applied': False, 'bidQty': round(qty_gc, 2), 'gcQty': gc_qty, 'variancePct': round(var, 2), 'thresholdPct': threshold_pct, 'adjustment': 0.0}
        if abs(var) > threshold_pct:
            lev = r2(amount / qty_gc * gc_qty)
            qn.update(applied=True, adjustment=r2(lev - amount))
            cell.update(value=lev, adjustment=r2(lev - amount))
        cell['qtyNorm'] = qn
    return cell


# ---------------------------------------------------------------- plugs
def _pool(item_key, me_id, bidders, cp):
    pool = []
    for b in bidders:
        if b['id'] == me_id:
            continue
        c = b['cells'][item_key]
        if c['state'] == 'priced' and c['value'] is not None:
            rate = c['unitNorm']['rateInGcUnit'] if c.get('unitNorm') and c['unitNorm'].get('rateInGcUnit') else None
            pool.append({'bidderId': b['id'], 'bidder': b['name'], 'value': c['value'], 'unitRate': rate})
    trimmed = []
    if cp.get('outlier_trim_pct') and len(pool) >= cp.get('outlier_trim_min_pool', 3):
        med = statistics.median(p['value'] for p in pool)
        if med:
            trimmed = [p for p in pool if abs(p['value'] - med) / med * 100 > cp['outlier_trim_pct']]
            pool = [p for p in pool if p not in trimmed]
    return pool, trimmed


def plug_value(step, item, pool, cp, ai):
    """One method attempt. Returns (value, formula) or (None, why it cannot be used)."""
    m = step['method']
    need = step.get('min_pool', cp.get('min_pool', 2))
    qty, unit = item.get('qty'), item.get('unit')
    if m == 'gc_estimate':
        if item.get('estimate') is None:
            return None, 'no GC estimate for this item'
        f = f"{qty:,.0f} {unit} x ${item['rate']:,.4f}" if qty and item.get('rate') else 'GC lump sum estimate'
        return r2(item['estimate']), f
    if m in ('fixed_allowance', 'manual'):
        if step.get('amount') is None:
            return None, 'no amount given'
        return r2(float(step['amount'])), 'amount entered by the estimator' if m == 'manual' else 'fixed allowance'
    if m in VALUE_METHODS:
        if len(pool) < need:
            return None, f'only {len(pool)} comparable price(s), {need} required'
        vals = [p['value'] for p in pool]
        return r2(STAT[VALUE_METHODS[m]](vals)), f"{VALUE_METHODS[m]} of " + ', '.join(f'${v:,.0f}' for v in vals)
    if m == 'unit_rate_x_gc_qty':
        src = step.get('rate_source', 'average')
        if not qty:
            return None, 'item has no GC quantity'
        if src == 'gc':
            return (r2(item['estimate']), 'GC rate x GC quantity') if item.get('estimate') is not None else (None, 'no GC rate')
        rates = [p['unitRate'] if p['unitRate'] is not None else p['value'] / qty for p in pool]
        if len(rates) < need:
            return None, f'only {len(rates)} comparable unit rate(s), {need} required'
        rate = STAT[src](rates)
        return r2(rate * qty), f"{src} of rates " + ', '.join(f'${x:,.2f}' for x in rates) + f" = ${rate:,.2f} x {qty:,.0f} {unit}"
    if m == 'ai_estimate':
        if not ai:
            return None, 'no AI estimate available'
        if ai.get('error') or ai.get('value') is None:
            return None, 'AI returned no usable estimate'
        if ai.get('confidence') == 'low':
            return None, 'AI confidence is low'
        if ai.get('unit_price') is not None and qty:
            return r2(ai['value']), f"AI estimate ${ai['unit_price']:,.2f}/{unit} x {qty:,.0f} {unit}"
        return r2(ai['value']), 'AI lump sum estimate'
    return None, f'unknown method {m}'


def plug_chain(item_key, cell, settings):
    """The ordered list of methods to try for a gap, from overrides, the AI switch and the plugging policy."""
    dflt = settings['default']
    rule = settings['items'].get(item_key) or {}
    first = {**rule, 'method': rule.get('method', dflt['method'])}
    chain = [first] + [s if isinstance(s, dict) else {'method': s} for s in rule.get('fallback', dflt['fallback'])]
    ov = cell.get('override')
    if ov and ov.get('action') == 'plug' and ov.get('method'):
        forced = {'method': ov['method'], 'min_pool': 1}
        if ov.get('amount') is not None:
            forced['amount'] = ov['amount']
        return [forced] + [s for s in chain if s['method'] != ov['method']]
    if settings.get('ai_auto') and first['method'] not in ('fixed_allowance', 'ai_estimate'):
        chain = [{'method': 'ai_estimate'}] + chain
    return chain


def needs_ai(items, bidders):
    """Item keys where a plug tried the AI estimate and had none. Run after a first leveling pass to know what to fetch."""
    keys = set()
    for it in items:
        for b in bidders:
            p = b['cells'][it['key']].get('plug')
            if p and any(a['method'] == 'ai_estimate' and a['result'] != 'used' for a in p['attempts']):
                keys.add(it['key'])
    return keys


def apply_plugs(items, bidders, settings, ai_prices):
    cp = settings['default']
    for b in bidders:
        for it in items:
            c = b['cells'][it['key']]
            if c['state'] != 'gap':
                continue
            pool, trimmed = _pool(it['key'], b['id'], bidders, cp)
            chain = plug_chain(it['key'], c, settings)
            ai = (ai_prices or {}).get(it['key'])
            attempts, value, used, formula = [], None, None, None
            for step in chain:
                value, formula = plug_value(step, it, pool, cp, ai)
                attempts.append({'method': step['method'], 'label': METHOD_LABEL.get(step['method'], step['method']),
                                 'result': 'used' if value is not None else 'skipped: ' + formula})
                if value is not None:
                    used = step['method']
                    break
            if value is None:        # last resort so a gap never silently counts as zero scope
                if pool:
                    value, used, formula = r2(statistics.fmean(p['value'] for p in pool)), 'average_of_bidders', 'average of the available prices (no policy method applied)'
                else:
                    value, used, formula = 0.0, 'none', 'no basis for a plug: no other prices, no GC estimate, no AI estimate'
                    c['flags'].append('No basis for a plug; carried at $0. Enter a value or add a GC estimate.')
                attempts.append({'method': used, 'label': METHOD_LABEL.get(used, used), 'result': 'used as last resort'})
            c['plug'] = {'method': used, 'label': METHOD_LABEL.get(used, 'No plug basis'), 'requested': chain[0]['method'], 'value': value, 'formula': formula,
                         'attempts': attempts, 'pool': pool, 'trimmed': trimmed, 'reason': c['gapReason'],
                         'ai': ai if used == 'ai_estimate' else None}
            c['value'] = value
            c['state'] = 'plugged'


# ---------------------------------------------------------------- whole package
def level(items, raw_bidders, settings=None, overrides=None, ai_prices=None):
    """items: baseline scope items. raw_bidders: [{id, name, cells: {key: extracted cell}, extras: [...]}].
    Returns {'bidders': [...], 'rows': {key: stats}, 'allowances': [...]} with every cell leveled."""
    settings = merged_settings(settings)
    ov = {}
    for o in overrides or []:
        ov[(o['bidder_id'], o['item_key'])] = o
    bidders = []
    for rb in raw_bidders:
        cells = {it['key']: normalize_cell(it, (rb.get('cells') or {}).get(it['key']), ov.get((rb['id'], it['key'])), settings['threshold_pct'])
                 for it in items}
        bidders.append({'id': rb['id'], 'name': rb['name'], 'cells': cells, 'extras': rb.get('extras') or []})
    apply_plugs(items, bidders, settings, ai_prices)

    # row statistics over the bidders' own prices (plugs are left out so they cannot pull the reference toward themselves)
    rows = {}
    for it in items:
        vals = sorted(b['cells'][it['key']]['value'] for b in bidders if b['cells'][it['key']]['state'] == 'priced')
        med = quant(vals, 0.5)
        ref = med if len(vals) >= 3 else (it.get('estimate') if it.get('estimate') else med)
        rows[it['key']] = {'n': len(vals), 'min': vals[0] if vals else None, 'q1': quant(vals, 0.25), 'med': med, 'q3': quant(vals, 0.75),
                           'max': vals[-1] if vals else None, 'ref': ref, 'refKind': 'median' if len(vals) >= 3 else 'GC estimate' if it.get('estimate') else 'median',
                           'plugged': sum(1 for b in bidders if b['cells'][it['key']]['state'] == 'plugged'),
                           'included': sum(1 for b in bidders if b['cells'][it['key']]['state'] == 'included'),
                           'unitNormalized': sum(1 for b in bidders if (b['cells'][it['key']].get('unitNorm') or {}).get('applied')),
                           'qtyNormalized': sum(1 for b in bidders if (b['cells'][it['key']].get('qtyNorm') or {}).get('applied'))}
        for b in bidders:
            c = b['cells'][it['key']]
            if c['value'] is not None and ref:
                c['dev'] = round(c['value'] / ref - 1, 4)
                c['cls'] = cls(c['dev'])
            else:
                c['dev'] = c['cls'] = None
            if c['state'] == 'priced' and vals:
                c['rank'] = 1 + sum(1 for v in vals if v < c['value'] - 1e-9)
                c['of'] = len(vals)
            else:
                c['rank'] = c['of'] = None

    weights = {it['key']: (it.get('estimate') or rows[it['key']]['med'] or 0) for it in items}
    wsum = sum(weights.values()) or 1.0
    allow = [{'name': a['name'], 'amount': r2(float(a['amount']))} for a in settings['allowances']]
    allow_total = r2(sum(a['amount'] for a in allow))
    for b in bidders:
        cs = b['cells'].values()
        extras = 0.0
        for e in b['extras']:
            amt = e.get('amount')
            if amt is None or e.get('treatment') not in ('add', 'credit'):
                continue
            extras += -abs(amt) if e.get('treatment') == 'credit' else amt
        as_bid_items = sum((c['asBid']['amount'] or 0) for c in cs if c['state'] == 'priced' and not (c['override'] and c['override']['action'] == 'manual_value' and c['status'] != 'priced'))
        manual_only = sum(c['value'] for c in cs if c['state'] == 'priced' and c['override'] and c['override']['action'] == 'manual_value' and c['status'] != 'priced')
        adj = sum(c['adjustment'] for c in cs if c['state'] == 'priced')
        plugs = sum(c['value'] for c in cs if c['state'] == 'plugged')
        lost = sum(weights[k] for k, c in b['cells'].items() if c['state'] == 'plugged')
        b.update(
            extrasTotal=r2(extras), asBid=r2(as_bid_items + extras), quantityAdjustments=r2(adj), manualAdded=r2(manual_only),
            plugs=r2(plugs + allow_total), itemPlugs=r2(plugs), allowanceTotal=allow_total,
            baseBid=r2(as_bid_items + extras + adj + manual_only),
            leveledTotal=r2(as_bid_items + extras + adj + manual_only + plugs + allow_total),
            scopePriced=round(1 - lost / wsum, 4),
            counts={'priced': sum(1 for c in cs if c['state'] == 'priced'), 'plugged': sum(1 for c in cs if c['state'] == 'plugged'),
                    'included': sum(1 for c in cs if c['state'] == 'included'),
                    'unitNormalized': sum(1 for c in cs if (c.get('unitNorm') or {}).get('applied')),
                    'qtyNormalized': sum(1 for c in cs if (c.get('qtyNorm') or {}).get('applied')),
                    'aiPlugs': sum(1 for c in cs if c['plug'] and c['plug']['method'] == 'ai_estimate')})
    return {'bidders': bidders, 'rows': rows, 'allowances': allow, 'settings': settings}
