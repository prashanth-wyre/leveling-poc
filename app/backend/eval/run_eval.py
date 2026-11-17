"""Run the real pipeline on the sample sets and compare with their answer keys.

    cd app/backend && uv run python eval/run_eval.py [scenario|workbook|all] [--fresh]

Scenario set (samples/tcjc_plugging): per-cell readings, bid totals, leveled values and plugs vs the answer key.
Workbook set (samples/tcjc): scope is read by the model from the scope sheet; bid totals vs the answer key.
"""
import json
import sys
import time

sys.path.insert(0, '.')
from wyre_level import config, db, engine, llm, seed  # noqa: E402
from wyre_level.pipeline import extract, run as runner  # noqa: E402


def close(a, b, tol=1.0):
    return a is not None and b is not None and abs(a - b) <= max(tol, 0.0005 * abs(b))


def scenario(report):
    root = config.SAMPLES / 'tcjc_plugging' / 'answer_key'
    proj = db.one("SELECT * FROM projects WHERE name='Teton County Justice Center'")
    for pk in db.many('SELECT * FROM packages WHERE project_id=? ORDER BY code', (proj['id'],)):
        slug = next(s for c, s, _ in seed.PACKAGES if c == pk['code'])
        key = json.loads((root / f'{slug}.json').read_text())
        t = time.time()
        res = runner.level_package(pk['id'])
        got = {extract.norm_name(b['name']): b for b in res['bidders']}
        row = {'package': f"{pk['code']} {pk['name']}", 'seconds': round(time.time() - t, 1), 'bidders': len(key['bidders']), 'found': 0,
               'as_bid_total_ok': 0, 'cells': 0, 'status_ok': 0, 'amount_ok': 0, 'priced_cells': 0, 'qty_unit_ok': 0, 'qty_cells': 0,
               'leveled_ok': 0, 'leveled_cells': 0, 'adjustment_flag_ok': 0, 'plug_cells': 0, 'plug_value_ok': 0, 'misses': []}
        for kb in key['bidders']:
            b = got.get(extract.norm_name(kb['company']))
            if not b:
                row['misses'].append(f"bidder not found: {kb['company']} (got {sorted(got)})")
                continue
            row['found'] += 1
            if close(b['asBid'], kb['bid_as_submitted']):
                row['as_bid_total_ok'] += 1
            else:
                row['misses'].append(f"{kb['company']}: as-bid total {b['asBid']:,.2f} vs key {kb['bid_as_submitted']:,.2f}")
            plugs = {p['item']: p for p in kb['plugs']}
            for ln in kb['lines']:
                c = b['cells'][ln['item']]
                row['cells'] += 1
                want_state = 'plugged' if ln['item'] in plugs else {'priced': 'priced', 'ls_noqty': 'priced', 'included': 'included'}.get(ln['status'], 'plugged')
                if c['state'] == want_state:
                    row['status_ok'] += 1
                else:
                    row['misses'].append(f"{kb['company']} / {ln['item']}: state {c['state']} vs key {want_state} ({ln['status']})")
                ab = ln['as_bid']
                if ln['status'] in ('priced', 'ls_noqty') and ln['item'] not in plugs:
                    row['priced_cells'] += 1
                    if close(c['asBid'].get('amount'), ab['amount']):
                        row['amount_ok'] += 1
                    else:
                        row['misses'].append(f"{kb['company']} / {ln['item']}: amount {c['asBid'].get('amount')} vs key {ab['amount']}")
                    if ab['qty'] is not None:
                        row['qty_cells'] += 1
                        if close(c['asBid'].get('qty'), ab['qty'], 0.01) and (c['asBid'].get('unit') or '').upper().rstrip('S') == (ab['unit'] or '').upper().rstrip('S'):
                            row['qty_unit_ok'] += 1
                        else:
                            row['misses'].append(f"{kb['company']} / {ln['item']}: qty/unit {c['asBid'].get('qty')} {c['asBid'].get('unit')} vs key {ab['qty']} {ab['unit']}")
                    row['leveled_cells'] += 1
                    if close(c['value'], ln['leveled_value']):
                        row['leveled_ok'] += 1
                    else:
                        row['misses'].append(f"{kb['company']} / {ln['item']}: leveled {c['value']} vs key {ln['leveled_value']}")
                    if bool((c.get('qtyNorm') or {}).get('applied')) == bool(ln['adjustment']):
                        row['adjustment_flag_ok'] += 1
                if ln['item'] in plugs:
                    row['plug_cells'] += 1
                    if c['state'] == 'plugged' and close(c['value'], plugs[ln['item']]['value']):
                        row['plug_value_ok'] += 1
                    elif c['state'] == 'plugged':
                        row['misses'].append(f"{kb['company']} / {ln['item']}: plug {c['value']:,.2f} ({c['plug']['method']}) vs key {plugs[ln['item']]['value']:,.2f} ({plugs[ln['item']]['method_used']})")
        key_low = min(key['bidders'], key=lambda x: x['base_bid_value'])['company']
        ours_low = min(res['bidders'], key=lambda x: x['leveledTotal'])['name']
        row['lowest_leveled'] = f"{ours_low} (key: {key_low})"
        row['recommended'] = next((b['name'] for b in res['bidders'] if b['id'] == res['recommendedId']), None)
        row['ordinals'] = [f"{c['ordinal']}. {c['name']} {c['weight']:g}%" for c in res['policy']['criteria']]
        row['gates'] = [g['name'] for g in res['policy']['gates']]
        row['flagged_cells'] = f"{res['summary']['flaggedCells']} of {res['summary']['cells']}"
        row['llm'] = res['run']
        report.append(row)


def workbook(report):
    root = config.SAMPLES / 'tcjc' / 'answer_key'
    proj = db.one("SELECT * FROM projects WHERE name LIKE '%workbook%'")
    for pk in db.many('SELECT * FROM packages WHERE project_id=? ORDER BY code', (proj['id'],)):
        slug = next(s for c, s, _ in seed.PACKAGES if c == pk['code'])
        key = json.loads((root / f'{slug}.json').read_text())
        if not (pk.get('scope') or {}).get('items'):
            doc = db.one("SELECT * FROM documents WHERE package_id=? AND kind='scope_sheet'", (pk['id'],))
            db.update('packages', pk['id'], scope={'items': extract.extract_scope(doc['path'])})
        t = time.time()
        res = runner.level_package(pk['id'])
        docs = {d['filename']: d for d in db.many('SELECT * FROM documents WHERE package_id=?', (pk['id'],))}
        row = {'package': f"{pk['code']} {pk['name']} (workbook set)", 'seconds': round(time.time() - t, 1), 'scope_items_read': len(res['items']),
               'bid_documents': 0, 'total_as_written_ok': 0, 'declines_expected': 0, 'declines_found': len(res['declined']),
               'superseded_expected': 0, 'superseded_found': len(res['superseded']), 'misses': []}
        for kb in key['bidders']:
            if kb['status'] == 'declined':
                row['declines_expected'] += 1
                continue
            for kd in kb['documents']:
                row['bid_documents'] += 1
                if kd['role'].startswith('superseded'):
                    row['superseded_expected'] += 1
                ext = (docs.get(kd['file']) or {}).get('extraction') or {}
                got = ext.get('stated_total') if ext.get('stated_total') is not None else ext.get('lines_total')
                if close(got, kd['total_as_written']):
                    row['total_as_written_ok'] += 1
                else:
                    row['misses'].append(f"{kd['file']}: total read {got} (lines {ext.get('lines_total')}) vs key {kd['total_as_written']}")
        row['recommended'] = next((b['name'] for b in res['bidders'] if b['id'] == res['recommendedId']), None)
        row['key_recommended'] = key['recommended_bidder']
        row['llm'] = res['run']
        report.append(row)


def twenty(report):
    """samples/tcjc_20: per-cell comparison of the AI reading and the leveled result with the answer key, plus qualification."""
    root = config.SAMPLES / 'tcjc_20' / 'answer_key'
    proj = db.one('SELECT * FROM projects WHERE name=?', (seed.TWENTY_NAME,))
    for pk in db.many('SELECT * FROM packages WHERE project_id=? ORDER BY code', (proj['id'],)):
        key = json.loads(next(f for f in root.glob('*.json') if f.name.startswith(pk['code'])).read_text())
        t = time.time()
        res = runner.level_package(pk['id'])
        got = {extract.norm_name(b['name']): b for b in res['bidders']}
        row = {'package': f"{pk['code']} {pk['name']} (20 bidders)", 'seconds': round(time.time() - t, 1), 'scope_items': len(key['items']),
               'bidders': len(key['bidders']), 'found': 0, 'as_bid_total_ok': 0, 'cells': 0, 'state_ok': 0, 'priced_cells': 0, 'amount_ok': 0,
               'qty_cells': 0, 'qty_unit_ok': 0, 'unit_normalized_cells': 0, 'unit_normalized_ok': 0, 'model_only_conversions': 0, 'model_only_ok': 0,
               'qty_reextended_cells': 0, 'qty_reextended_ok': 0, 'leveled_ok': 0, 'plug_cells': 0, 'plug_value_ok': 0,
               'declines_found': f"{len(res['declined'])} of {len(key['declined'])}", 'superseded_found': f"{len(res['superseded'])} of {len(key['superseded'])}",
               'qualification_agrees': 0, 'misses': []}
        exp_q = {}
        for kb in key['bidders']:
            b = got.get(extract.norm_name(kb['company']))
            exp_q[kb['company']] = kb['qualification']['expected_qualified']
            if not b:
                row['misses'].append(f"bidder not found: {kb['company']}")
                continue
            row['found'] += 1
            if close(b['asBid'], kb['as_bid_total']):
                row['as_bid_total_ok'] += 1
            else:
                row['misses'].append(f"{kb['company']}: as-bid total {b['asBid']:,.2f} vs key {kb['as_bid_total']:,.2f}")
            if b['qualified'] == kb['qualification']['expected_qualified']:
                row['qualification_agrees'] += 1
            else:
                row['misses'].append(f"{kb['company']}: qualified={b['qualified']} vs expected {kb['qualification']['expected_qualified']} "
                                     f"(app: {'; '.join(b['reasons'])[:160] or 'no failed rule'}; key: {'; '.join(kb['qualification']['disqualified_because']) or 'none'})")
            for ln in kb['lines']:
                c = b['cells'][ln['item']]
                row['cells'] += 1
                if c['state'] == ln['state']:
                    row['state_ok'] += 1
                else:
                    row['misses'].append(f"{kb['company']} / {ln['item']}: state {c['state']} vs key {ln['state']} ({ln['status']})")
                ab = ln['as_bid']
                if ln['status'] == 'priced':
                    row['priced_cells'] += 1
                    row['amount_ok'] += close(c['asBid'].get('amount'), ab['amount'])
                    if not close(c['asBid'].get('amount'), ab['amount']):
                        row['misses'].append(f"{kb['company']} / {ln['item']}: amount {c['asBid'].get('amount')} vs key {ab['amount']}")
                    if ab['quantity'] is not None:
                        row['qty_cells'] += 1
                        ok = close(c['asBid'].get('qty'), ab['quantity'], 0.01) and engine.norm_unit(c['asBid'].get('unit')) == engine.norm_unit(ab['unit'])
                        row['qty_unit_ok'] += ok
                        if not ok:
                            row['misses'].append(f"{kb['company']} / {ln['item']}: qty/unit {c['asBid'].get('qty')} {c['asBid'].get('unit')} vs key {ab['quantity']} {ab['unit']}")
                    if ln['conversion']:
                        row['unit_normalized_cells'] += 1
                        un = c.get('unitNorm') or {}
                        ok = bool(un.get('applied')) and abs(un['factor'] / ln['conversion']['factor'] - 1) < 0.01
                        row['unit_normalized_ok'] += ok
                        if 'stated in the bid' in ln['conversion']['source']:
                            row['model_only_conversions'] += 1
                            row['model_only_ok'] += ok
                        if not ok:
                            row['misses'].append(f"{kb['company']} / {ln['item']}: conversion {un.get('factor')} vs key {ln['conversion']['factor']} ({ln['conversion']['explanation']})")
                    if (ln['quantity_check'] or {}).get('applied'):
                        row['qty_reextended_cells'] += 1
                        row['qty_reextended_ok'] += bool((c.get('qtyNorm') or {}).get('applied'))
                    row['leveled_ok'] += close(c['value'], ln['leveled_value'])
                if ln['plug']:
                    row['plug_cells'] += 1
                    if c['state'] == 'plugged' and close(c['value'], ln['plug']['value']):
                        row['plug_value_ok'] += 1
                    elif c['state'] == 'plugged':
                        row['misses'].append(f"{kb['company']} / {ln['item']}: plug {c['value']:,.2f} ({c['plug']['method']}) vs key {ln['plug']['value']:,.2f} ({ln['plug']['method']})")
        rec = next((b['name'] for b in res['bidders'] if b['id'] == res['recommendedId']), None)
        row['recommended'] = rec
        row['expected_recommendation'] = key['expected']['acceptable_recommendations']
        row['recommendation_ok'] = extract.norm_name(rec or '') in {extract.norm_name(x) for x in key['expected']['acceptable_recommendations']}
        row['qualified_app_vs_key'] = f"{res['summary']['qualified']} vs {key['expected']['qualified_count']}"
        row['ordinals'] = [f"{c['ordinal']}. {c['name']} {c['weight']:g}%" for c in res['policy']['criteria']]
        row['flagged_cells'] = f"{res['summary']['flaggedCells']} of {res['summary']['cells']}"
        row['llm'] = res['run']
        report.append(row)


if __name__ == '__main__':
    which = next((a for a in sys.argv[1:] if not a.startswith('-')), 'all')
    db.conn()
    seed.seed(reset='--fresh' in sys.argv)
    report = []
    if which in ('scenario', 'all'):
        scenario(report)
    if which in ('workbook', 'all'):
        workbook(report)
    if which in ('twenty', 'all'):
        twenty(report)
    for r in report:
        misses = r.pop('misses')
        print('\n' + json.dumps(r, indent=1))
        for m in misses[:60]:
            print('  MISS', m)
    print('\nLLM totals this run:', llm.stats)
