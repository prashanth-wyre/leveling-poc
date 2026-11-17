"""Resolve bid specs against the workbook and derive the leveled figures."""
from tcjc import shift, key_rows, bidders

SYNTH_NOTICE = ('SYNTHETIC TEST DATA - generated for bid-leveling POC testing; '
                'not an actual proposal from the named firm.')


class Check(Exception):
    pass


def near(a, b, tol=0.011):
    return abs(a - b) <= tol


def money(x, dec=None, sym='$'):
    if dec is None:
        dec = 0 if near(x, round(x), 0.001) else 2
    s = f'{abs(x):,.{dec}f}'
    return f'({sym}{s})' if x < 0 else f'{sym}{s}'


def qty_str(q):
    if q is None:
        return ''
    return f'{q:,.0f}' if near(q, round(q), 0.001) else f'{q:,.2f}'


def load_package(wb, code, spec):
    tab = wb.tab(spec['sheet'])
    k = key_rows(tab)
    missing = {'base', 'subvalue', 'total', 'textura', 'tax', 'sdi', 'rec', 'alt', 'allow', 'pba', 'ctc', 'ack', 'div'} - set(k)
    if missing:
        raise Check(f'{code}: summary rows not found: {missing}')
    eb = spec['est_block']
    return dict(spec, code=code, tab=tab, k=k, bidders=bidders(tab, eb), estimate=tab.money(eb, k['subvalue']))


def resolve(bid, pkg):
    """Fill line values from workbook cells; verify they tie to the workbook's summary rows."""
    tab, k, b = pkg['tab'], pkg['k'], bid['block']
    cq, cu, cp, cv = (shift(b, i) for i in (1, 2, 3, 4))
    name = tab.text(b, 2)
    if name != bid['company']:
        raise Check(f"{bid['id']}: block {b} is {name!r}, not {bid['company']!r}")
    lines, total = [], 0.0
    for sp in bid['lines']:
        r = sp['row']
        amt = tab.v(cv, r) if sp['amt'] == 'wb' else sp['amt']
        if amt is None:
            raise Check(f"{bid['id']}: no value in {cv}{r}")
        if isinstance(amt, float):
            amt = round(amt, 2)
            total += amt
        qty = tab.num(cq, r) if sp['qty'] == 'wb' else sp['qty']
        unit = tab.text(cu, r) if sp['unit'] == 'wb' else sp['unit']
        up = tab.num(cp, r) if sp['up'] == 'wb' else sp['up']
        desc = sp['desc'].format(up=up) if '{up' in sp['desc'] else sp['desc']
        show_up = None
        if up is not None and qty and isinstance(amt, float) and '{up' not in sp['desc']:
            if near(qty * up, amt, 0.5) or sp['force_up']:
                show_up = round(up, 2)
        if qty is not None and not isinstance(amt, float) and sp['qty'] == 'wb':
            qty, unit = None, None          # "Included" lines carry no quantity
        if unit:
            unit = unit.strip('.').upper()
            unit = {'SQS': 'SQ', 'TREES': 'TREES'}.get(unit, unit)
        lines.append(dict(row=r, scope_item=tab.text('C', r), desc=desc, qty=qty, unit=unit if qty is not None else None,
                          up=show_up, amt=amt, sec=sp['sec']))
    total = round(total, 2)
    if not near(total, bid['expect']):
        raise Check(f"{bid['id']}: lines sum to {total}, spec expects {bid['expect']}")
    out = dict(bid, lines=lines, total=total, superseded=bool(bid.get('superseded_by')))
    out['alts'] = [dict(row=r, desc=d, amt=tab.money(cv, r)) for r, d in bid['alts']]
    if any(a['amt'] is None for a in out['alts']):
        raise Check(f"{bid['id']}: alternate has no workbook value")
    out['tax_add'] = tab.money(cv, bid['tax_row']) if bid.get('tax_row') else None
    if bid['plugs'] is None:
        return out
    # The workbook only codes cost categories (52 = contingency) for the recommended bidder's column.
    cat_col = shift(pkg['est_block'], 6)
    rec_val = next(shift(blk, 4) for blk, nm in pkg['bidders'] if tab.text(blk, k['rec']) == nm)
    plugs = []
    for r in bid['plugs']:
        amt = tab.money(cv, r)
        coded = tab.num(cat_col, r) == 52 and tab.money(rec_val, r) == amt
        plugs.append(dict(row=r, scope_item=tab.text('C', r), amt=amt,
                          basis='workbook cost category 52 (contingency)' if coded else 'inferred from workbook values'))
    lev = dict(
        sub_bid_as_submitted=total, gc_plugs=plugs, gc_plug_total=round(sum(p['amt'] for p in plugs), 2),
        base_bid_value=tab.money(cv, k['base']), textura=tab.money(cv, k['textura']) or 0.0,
        subcontract_value=tab.money(b, k['subvalue']), sales_tax=tab.money(cv, k['tax']) or 0.0,
        sdi=tab.money(cv, k['sdi']) or 0.0, total_package_value=tab.money(b, k['total']),
    )
    if not near(total + lev['gc_plug_total'], lev['base_bid_value']):
        raise Check(f"{bid['id']}: bid {total} + plugs {lev['gc_plug_total']} != workbook base {lev['base_bid_value']}")
    if not near(lev['base_bid_value'] + lev['textura'], lev['subcontract_value'], 0.02):
        raise Check(f"{bid['id']}: base + Textura != subcontract value")
    if not near(lev['subcontract_value'] + lev['sales_tax'] + lev['sdi'], lev['total_package_value'], 0.02):
        raise Check(f"{bid['id']}: subcontract value + tax + SDI != total package value")
    lev['variance'] = round(lev['total_package_value'] - pkg['estimate'], 2)
    lev['variance_pct'] = round(lev['variance'] / pkg['estimate'] * 100, 1)
    out['lev'] = lev
    return out


def table_rows(bid):
    """Flatten lines into ('sec', title) / ('line', n, desc, qty, unit, unit price, amount) tuples."""
    rows, sec, n = [], None, 0
    dec = 2 if any(isinstance(l['amt'], float) and not near(l['amt'], round(l['amt']), 0.001) for l in bid['lines']) else 0
    for l in bid['lines']:
        if l['sec'] and l['sec'] != sec:
            sec = l['sec']
            rows.append(('sec', sec))
        n += 1
        amt = money(l['amt'], dec) if isinstance(l['amt'], float) else l['amt']
        rows.append(('line', n, l['desc'], qty_str(l['qty']), l['unit'] or '',
                     money(l['up'], 2) if l['up'] is not None else '', amt))
    return rows, dec


def tax_text(bid):
    return {
        'excluded': 'Sales tax is excluded. Pricing is based on the project being tax exempt.',
        'included': 'All prices include applicable sales tax.',
        'silent': None,
        'add': f"Sales tax on materials is NOT included in the total: add {money(bid['tax_add'], 2)} if applicable."
               if bid.get('tax_add') else None,
    }[bid['tax']]
