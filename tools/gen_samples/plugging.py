"""Reference plugging engine: unit conversion, quantity normalization, plug methods, totals, sensitivity."""
import statistics

from tcjc import shift

AREA = {'SF': 1.0, 'SQ': 100.0, 'SY': 9.0, 'M2': 10.7639, 'ROLL': 10.0}
LENGTH = {'LF': 1.0, 'FT': 1.0, 'PANEL': 8.0}
STAT = {'min': min, 'max': max, 'average': statistics.fmean, 'median': statistics.median}
VALUE_METHODS = {'min_of_bidders': 'min', 'max_of_bidders': 'max', 'average_of_bidders': 'average', 'median_of_bidders': 'median'}


def to_gc(qty, unit, gc_unit, depth=None, gc_depth=None):
    """Convert a quoted quantity to the GC unit. Returns (quantity, explanation)."""
    unit, gc_unit = unit.upper(), gc_unit.upper()
    d = depth or gc_depth
    if unit in AREA and gc_unit == 'SF':
        q, why = qty * AREA[unit], f'{unit} x {AREA[unit]:g} = SF' if unit != 'SF' else 'same unit'
        if gc_depth and d != gc_depth:
            q, why = q * d / gc_depth, f'{why}; {d:g} in. depth vs {gc_depth:g} in. specified: x {d:g}/{gc_depth:g}'
        return q, why
    if unit == 'CY' and gc_unit == 'SF':
        return qty * 324.0 / d, f'CY x 324 / {d:g} in. = SF'
    if unit in AREA and gc_unit == 'CY':
        return qty * AREA[unit] * d / 324.0, f'SF x {d:g} in. / 324 = CY'
    if unit in LENGTH and gc_unit == 'LF':
        return qty * LENGTH[unit], f'{unit} x {LENGTH[unit]:g} = LF' if LENGTH[unit] != 1 else 'same length unit'
    if unit == gc_unit:
        return float(qty), 'same unit'
    raise ValueError(f'no conversion {unit} -> {gc_unit}')


def r2(x):
    return round(x + 1e-9, 2)


# ------------------------------------------------------------------ resolve specs against the workbook
def resolve_items(pkg, items, synthetic):
    t, eb = pkg['tab'], pkg['est_block']
    cq, cp, cv = shift(eb, 1), shift(eb, 3), shift(eb, 4)
    out = {}
    for it in items:
        d = dict(key=it['key'], desc=it['desc'], unit=it['unit'], depth=it['depth'],
                 source='synthetic' if it['key'] in synthetic else 'TCJC workbook estimate block')

        def val(x):
            if not isinstance(x, tuple):
                return x
            kind, a = x
            if kind == 'q':
                return sum(t.num(cq, r) for r in a)
            return t.num(cp, a) if kind == 'p' else t.money(cv, a)
        if it['unit'] == 'LS':
            d.update(qty=None, rate=None, estimate=r2(val(it['ls'])))
        else:
            qty = val(it['qty'])
            rate = val(it['rate'])
            if isinstance(it['rate'], tuple) and it['rate'][0] == 'v':
                rate = rate / qty
            d.update(qty=qty, rate=round(rate, 4), estimate=r2(qty * rate))
        out[it['key']] = d
    return out


def resolve_bid(spec, pkg, items):
    """Turn a bid spec into priced lines exactly as they appear in the bid document."""
    t, b = pkg['tab'], spec['src']
    cq, cv = shift(b, 1), shift(b, 4)

    def wb(ref, gc_qty):
        if not isinstance(ref, tuple):
            return float(ref)
        _, rows, div = ref
        total = sum(t.money(cv, r) for r in rows)
        if div == 'gc':
            return total / gc_qty if gc_qty else total
        return total / (t.num(cq, rows[0]) if div == 'own' else div)
    lines = []
    for s in spec['lines']:
        it = items[s['item']]
        ln = dict(item=it['key'], desc=s['desc'] or it['desc'], status=s['status'], qty=None, unit=None, up=None, amt=None,
                  depth=s['depth'], sec=None, row=None)
        if s['status'] == 'priced':
            per, _ = to_gc(1, s['unit'], it['unit'], s['depth'], it['depth'])     # GC units per quoted unit
            ln.update(qty=float(s['qty']), unit=s['unit'], up=r2(wb(s['rate'], it['qty']) * per))
            ln['amt'] = r2(ln['qty'] * ln['up'])
        elif s['status'] == 'ls_noqty':
            ln['amt'] = r2(wb(s['amount'], None))
        elif s['status'] == 'included':
            ln['amt'] = 'Included'
        lines.append(ln)
    shown = [l for l in lines if l['amt'] is not None]
    excl = [items[l['item']]['desc'] for l in lines if l['status'] == 'excluded'] + spec['excl_extra']
    return dict(spec, all_lines=lines, lines=shown, total=r2(sum(l['amt'] for l in shown if isinstance(l['amt'], float))),
                excl=excl, tax_add=None, responsive=True)


# ------------------------------------------------------------------ leveling
def normalize(bid, items, qn):
    """Quantity normalization of every line. Adds 'lev' (leveled value) and audit fields."""
    out = []
    for l in bid['all_lines']:
        it = items[l['item']]
        e = dict(item=l['item'], status=l['status'], as_bid=dict(qty=l['qty'], unit=l['unit'], unit_price=l['up'], amount=l['amt'],
                                                                 stated_depth_in=l['depth']),
                 gc=dict(qty=it['qty'], unit=it['unit']), converted_qty=None, conversion=None, variance_pct=None,
                 unit_rate_in_gc_unit=None, action='n/a', leveled_value=None, adjustment=0.0)
        if l['status'] == 'priced':
            q, why = to_gc(l['qty'], l['unit'], it['unit'], l['depth'], it['depth'])
            rate = l['amt'] / q
            var = (q - it['qty']) / it['qty'] * 100
            e.update(converted_qty=round(q, 2), conversion=why, variance_pct=round(var, 2), unit_rate_in_gc_unit=round(rate, 4))
            if abs(var) > qn['threshold_pct']:
                lev = r2(rate * it['qty'])
                e.update(action='re-extended at GC quantity', leveled_value=lev, adjustment=r2(lev - l['amt']))
            else:
                e.update(action='carried as bid (within threshold)', leveled_value=l['amt'])
        elif l['status'] == 'ls_noqty':
            e.update(action='lump sum without quantity - flag only' if it['qty'] else 'lump sum item - carried as bid',
                     leveled_value=l['amt'], unit_rate_in_gc_unit=round(l['amt'] / it['qty'], 4) if it['qty'] else None)
        elif l['status'] == 'included':
            e['action'] = 'included in other lines - no value'
        else:
            e['action'] = 'gap - ' + ('excluded by bidder' if l['status'] == 'excluded' else 'not priced')
        out.append(e)
    return out


def _pool(item, me, norm, bids, cp):
    pool = []
    for b in bids:
        if b['company'] == me or (cp['exclude_unresponsive'] and not b['responsive']):
            continue
        e = next(x for x in norm[b['id']] if x['item'] == item['key'])
        if e['leveled_value'] is not None:
            pool.append(dict(bidder=b['company'], value=e['leveled_value'], unit_rate=e['unit_rate_in_gc_unit']))
    trimmed = []
    if cp['outlier_trim_pct'] and len(pool) >= cp['outlier_trim_min_pool']:
        med = statistics.median(p['value'] for p in pool)
        trimmed = [p for p in pool if abs(p['value'] - med) / med * 100 > cp['outlier_trim_pct']]
        pool = [p for p in pool if p not in trimmed]
    return pool, trimmed


def plug_value(step, item, pool, cp, ai):
    """One method attempt. Returns (value, formula) or (None, reason it cannot be used)."""
    m = step['method']
    need = step.get('min_pool', cp['min_pool'])
    if m == 'gc_estimate':
        f = f"{item['qty']:,.0f} {item['unit']} x ${item['rate']:,.4f}" if item['qty'] else 'GC lump sum estimate'
        return item['estimate'], f
    if m == 'fixed_allowance':
        return float(step['amount']), 'fixed allowance'
    if m in VALUE_METHODS:
        if len(pool) < need:
            return None, f'only {len(pool)} comparable price(s), {need} required'
        vals = [p['value'] for p in pool]
        return r2(STAT[VALUE_METHODS[m]](vals)), f"{VALUE_METHODS[m]} of " + ', '.join(f'${v:,.2f}' for v in vals)
    if m == 'unit_rate_x_gc_qty':
        src = step.get('rate_source', 'average')
        if src == 'gc':
            return item['estimate'], 'GC rate x GC quantity'
        rates = [p['unit_rate'] for p in pool if p['unit_rate'] is not None]
        if len(rates) < need:
            return None, f'only {len(rates)} comparable unit rate(s), {need} required'
        rate = STAT[src](rates)
        return r2(rate * item['qty']), f"{src} of rates " + ', '.join(f'${x:,.4f}' for x in rates) + f" = ${rate:,.4f} x {item['qty']:,.0f} {item['unit']}"
    if m == 'ai_market_price':
        if not ai:
            return None, 'no AI price available (no API key or snapshot)'
        if ai.get('error') or ai.get('unit_price') is None:
            return None, 'AI returned no usable price'
        if len(ai.get('sources', [])) < step['_ai']['min_sources']:
            return None, f"AI cited {len(ai.get('sources', []))} source(s), {step['_ai']['min_sources']} required"
        if ai.get('confidence', 'low') == 'low':
            return None, 'AI confidence is low'
        return r2(ai['unit_price'] * item['qty']), f"AI market price ${ai['unit_price']:,.2f}/{item['unit']} x {item['qty']:,.0f} {item['unit']}"
    raise ValueError(m)


def level(pkg_code, bids, items, policy, textura_rate, sdi_rate, ai_prices, force_method=None):
    """Level one package. force_method replaces every policy gap rule (used for the sensitivity table)."""
    pp, dflt = policy['packages'][pkg_code], policy['defaults']
    cp = dflt['comparable_pool']
    norm = {b['id']: normalize(b, items, policy['quantity_normalization']) for b in bids}
    results = []
    for b in bids:
        plugs = []
        for e in norm[b['id']]:
            it = items[e['item']]
            over = next((o for o in pp.get('manual_overrides', []) if o['bidder'] == b['company'] and o['item'] == it['key']), None)
            if over:
                plugs.append(dict(item=it['key'], reason='manual override: ' + over['reason'], method_requested='fixed_allowance',
                                  method_used='fixed_allowance', attempts=[], pool=[], trimmed_outliers=[], formula='manual override',
                                  value=float(over['amount'])))
                continue
            if e['status'] not in ('excluded', 'omitted'):
                continue
            rule = pp['items'].get(it['key'], {})
            first = dict(rule, method=rule.get('method', dflt['method']))
            chain = [first] + [s if isinstance(s, dict) else {'method': s} for s in rule.get('fallback', dflt['fallback'])]
            if force_method:
                chain = [{'method': force_method, 'min_pool': 1}, {'method': 'gc_estimate'}]
            pool, trimmed = _pool(it, b['company'], norm, bids, cp)
            ai = ai_prices.get(f'{pkg_code}/{it["key"]}')
            attempts, value, used, formula = [], None, None, None
            for step in chain:
                step = dict(step, _ai=policy['ai_market_price'])
                value, formula = plug_value(step, it, pool, cp, ai)
                attempts.append(dict(method=step['method'], result='used' if value is not None else 'skipped: ' + formula))
                if value is not None:
                    used = step['method']
                    break
            p = dict(item=it['key'], reason='excluded by bidder' if e['status'] == 'excluded' else 'not priced',
                     method_requested=chain[0]['method'], method_used=used, attempts=attempts, pool=pool, trimmed_outliers=trimmed,
                     formula=formula, value=value)
            if used == 'ai_market_price':
                band = policy['ai_market_price']['acceptance_band_pct'] / 100
                p['ai'] = dict(ai, acceptance_band=[r2(value * (1 - band)), r2(value * (1 + band))])
                if pool:
                    avg = statistics.fmean(x['value'] for x in pool)
                    dev = (value - avg) / avg * 100
                    if abs(dev) > policy['ai_market_price']['flag_if_deviation_from_bidder_average_pct']:
                        p['flag'] = f'AI price is {dev:+.0f}% vs the bidders\' average (${avg:,.2f})'
            plugs.append(p)
        allow = [dict(a) for a in pp['allowances_all_bidders']]
        as_bid = b['total']
        adj = r2(sum(e['adjustment'] for e in norm[b['id']]))
        base = r2(as_bid + adj + sum(p['value'] for p in plugs) + sum(a['amount'] for a in allow))
        textura = r2(base * textura_rate)
        sub = r2(base + textura)
        sdi = r2(sub * sdi_rate)
        flags = [f"{e['item']}: quantity {e['variance_pct']:+.1f}% vs GC takeoff after converting {e['as_bid']['unit']} - "
                 f"re-extended, {e['adjustment']:+,.2f}" for e in norm[b['id']] if e['adjustment']]
        flags += [f"{e['item']}: lump sum with no quantity - cannot check against GC takeoff" for e in norm[b['id']]
                  if e['action'].startswith('lump sum without')]
        flags += [f"{p['item']}: {p['reason']} - plugged ${p['value']:,.2f} by {p['method_used']}" for p in plugs]
        results.append(dict(company=b['company'], document=b['file'], format=b['fmt'], responsive=b['responsive'],
                            lines=norm[b['id']], bid_as_submitted=as_bid, quantity_adjustments=adj, plugs=plugs,
                            plug_total=r2(sum(p['value'] for p in plugs)), allowances=allow,
                            allowance_total=r2(sum(a['amount'] for a in allow)), base_bid_value=base, textura=textura,
                            subcontract_value=sub, sdi=sdi, total_package_value=r2(sub + sdi), expected_flags=flags))
    rank = sorted((r for r in results if r['responsive']), key=lambda r: r['total_package_value'])
    return dict(bidders=results, recommended_bidder=rank[0]['company'],
                ranking=[dict(company=r['company'], total_package_value=r['total_package_value']) for r in rank])


def sensitivity(pkg_code, bids, items, policy, trate, sdi, ai_prices):
    out = {}
    for label, m in [('policy as written', None), ('gc_estimate', 'gc_estimate'), ('min_of_bidders', 'min_of_bidders'),
                     ('average_of_bidders', 'average_of_bidders'), ('median_of_bidders', 'median_of_bidders'),
                     ('max_of_bidders', 'max_of_bidders')]:
        res = level(pkg_code, bids, items, policy, trate, sdi, ai_prices, force_method=m)
        out[label] = dict(recommended_bidder=res['recommended_bidder'],
                          totals={r['company']: r['total_package_value'] for r in res['bidders']})
    return out


# ------------------------------------------------------------------ hand-computed checks
def selftest():
    def close(a, b, tol=0.01):
        assert abs(a - b) <= tol, (a, b)
    close(to_gc(288, 'SQ', 'SF')[0], 28800)
    close(to_gc(424, 'SY', 'SF')[0], 3816)
    close(to_gc(2676, 'M2', 'SF')[0], 28804.20, 0.01)
    close(to_gc(47, 'CY', 'SF', gc_depth=3)[0], 5076)
    close(to_gc(5104, 'SF', 'SF', depth=2, gc_depth=3)[0], 3402.67)
    close(to_gc(2052, 'SF', 'CY', depth=3, gc_depth=3)[0], 19.0)
    close(to_gc(400, 'ROLL', 'SF')[0], 4000)
    close(to_gc(15, 'PANEL', 'LF')[0], 120)
    items = {'X': dict(key='X', desc='x', unit='SF', qty=1000.0, rate=2.0, estimate=2000.0, depth=None),
             'Y': dict(key='Y', desc='y', unit='LS', qty=None, rate=None, estimate=500.0, depth=None)}

    def mk(name, qty, up, y):
        ln = [dict(item='X', status='priced', qty=qty, unit='SF', up=up, amt=r2(qty * up), depth=None)]
        ln.append(dict(item='Y', status='ls_noqty' if y else 'excluded', qty=None, unit=None, up=None, amt=y, depth=None))
        return dict(id=name, company=name, file='', fmt='', responsive=True, all_lines=ln,
                    total=r2(qty * up + (y or 0)))
    bids = [mk('A', 1049, 1.0, None), mk('B', 1060, 1.0, 10.0), mk('C', 1000, 1.0, 20.0), mk('D', 1000, 1.0, 60.0)]
    pol = {'defaults': {'method': 'average_of_bidders', 'fallback': ['gc_estimate'],
                        'comparable_pool': {'exclude_self': True, 'exclude_unresponsive': True, 'min_pool': 2,
                                            'outlier_trim_pct': 50, 'outlier_trim_min_pool': 3}},
           'quantity_normalization': {'threshold_pct': 5.0}, 'ai_market_price': {'min_sources': 2, 'acceptance_band_pct': 25,
                                                                                  'flag_if_deviation_from_bidder_average_pct': 25},
           'packages': {'T': {'allowances_all_bidders': [], 'items': {}}}}
    res = {r['company']: r for r in level('T', bids, items, pol, 0, 0, {})['bidders']}
    close(res['A']['quantity_adjustments'], 0)              # 4.9% over: carried as bid
    close(res['B']['quantity_adjustments'], -60)            # 6.0% over: re-extended at 1,000 SF
    # A's gap on Y: pool 10, 20, 60 -> median 20 -> 60 is 200% away, trimmed -> average(10, 20) = 15
    close(res['A']['plugs'][0]['value'], 15)
    assert [p['bidder'] for p in res['A']['plugs'][0]['trimmed_outliers']] == ['D']
    for m, want in [('min_of_bidders', 10), ('max_of_bidders', 20), ('median_of_bidders', 15), ('gc_estimate', 500)]:
        got = {r['company']: r for r in level('T', bids, items, pol, 0, 0, {}, force_method=m)['bidders']}['A']['plugs'][0]['value']
        close(got, want)
    two = [bids[0], bids[1]]                                 # pool of one -> average needs two -> falls back to GC estimate
    p = {r['company']: r for r in level('T', two, items, pol, 0, 0, {})['bidders']}['A']['plugs'][0]
    assert p['method_used'] == 'gc_estimate' and p['value'] == 500.0, p
    return 'engine self-test passed (8 conversions, threshold, trim, min/max/median/average, fallback)'
