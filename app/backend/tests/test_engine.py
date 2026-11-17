"""Hand-computed checks on the deterministic engine and the scoring."""
from wyre_level import engine
from wyre_level.pipeline import assess, policy as policy_mod


def close(a, b, tol=0.011):
    assert abs(a - b) <= tol, (a, b)


def test_table_conversions():
    close(288 * engine.table_factor('SQ', 'SF')[0], 28800)
    close(424 * engine.table_factor('sy', 'SF')[0], 3816)
    close(2676 * engine.table_factor('m2', 'SF')[0], 28804.20)
    close(47 * engine.table_factor('CY', 'SF', None, 3)[0], 5076)
    close(5104 * engine.table_factor('SF', 'SF', 2, 3)[0], 3402.67)
    close(2052 * engine.table_factor('SF', 'CY', 3, 3)[0], 19.0)
    close(400 * engine.table_factor('rolls', 'SF')[0], 4000)
    close(15 * engine.table_factor('Panel', 'LF')[0], 120)
    close(100 * engine.table_factor('m3', 'CY')[0], 130.795)
    close(100 * engine.table_factor('M', 'LF')[0], 328.084)
    assert engine.table_factor('PALLET', 'SF') is None
    assert engine.norm_unit('Sq. Ft.') == 'SF' and engine.norm_unit('squares') == 'SQ'


ITEMS = [{'key': 'X', 'name': 'x', 'unit': 'SF', 'qty': 1000.0, 'rate': 2.0, 'estimate': 2000.0, 'depth': None},
         {'key': 'Y', 'name': 'y', 'unit': 'LS', 'qty': None, 'rate': None, 'estimate': 500.0, 'depth': None}]


def bidder(name, qty, up, y, unit='SF', factor=None):
    x = {'status': 'priced', 'quantity': qty, 'unit': unit, 'unit_price': up, 'amount': round(qty * up, 2), 'confidence': 1, 'gc_units_per_bid_unit': factor}
    yc = {'status': 'priced', 'amount': y, 'confidence': 1} if y is not None else {'status': 'excluded', 'confidence': 1}
    return {'id': name, 'name': name, 'cells': {'X': x, 'Y': yc}, 'extras': []}


FIELD = [bidder('A', 1049, 1.0, None), bidder('B', 1060, 1.0, 10.0), bidder('C', 1000, 1.0, 20.0), bidder('D', 1000, 1.0, 60.0)]


def by(res):
    return {b['id']: b for b in res['bidders']}


def test_quantity_threshold():
    r = by(engine.level(ITEMS, FIELD))
    assert r['A']['cells']['X']['qtyNorm']['applied'] is False        # 4.9% over: carried as bid
    close(r['A']['quantityAdjustments'], 0)
    assert r['B']['cells']['X']['qtyNorm']['applied'] is True         # 6.0% over: re-extended at 1,000 SF
    close(r['B']['quantityAdjustments'], -60)
    close(r['B']['cells']['X']['value'], 1000)


def test_plug_methods_trim_and_fallback():
    r = by(engine.level(ITEMS, FIELD))
    p = r['A']['cells']['Y']['plug']
    close(p['value'], 15)                                             # pool 10, 20, 60: 60 trimmed, average of 10 and 20
    assert [x['bidder'] for x in p['trimmed']] == ['D']
    for method, want in [('min_of_bidders', 10), ('max_of_bidders', 20), ('median_of_bidders', 15), ('gc_estimate', 500)]:
        got = by(engine.level(ITEMS, FIELD, {'default': {'method': method, 'fallback': ['gc_estimate'], 'min_pool': 1}}))['A']['cells']['Y']['plug']['value']
        close(got, want)
    p2 = by(engine.level(ITEMS, FIELD[:2]))['A']['cells']['Y']['plug']  # one comparable price: average needs two, GC estimate used
    assert p2['method'] == 'gc_estimate' and p2['value'] == 500.0
    assert p2['attempts'][0]['result'].startswith('skipped')


def test_unit_normalization_table_and_llm():
    sq = bidder('S', 10, 150.0, 5.0, unit='SQ', factor=100)           # 10 squares = 1,000 SF
    r = by(engine.level(ITEMS, [sq, FIELD[2], FIELD[3]]))
    u = r['S']['cells']['X']['unitNorm']
    assert u['applied'] and u['source'] == 'table' and u['factor'] == 100
    close(u['rateInGcUnit'], 1.5)
    odd = bidder('P', 20, 60.0, 5.0, unit='PALLET', factor=40)        # unknown unit: the model's factor is used (20 x 40 = 800 SF)
    c = by(engine.level(ITEMS, [odd, FIELD[2], FIELD[3]]))['P']['cells']['X']
    assert c['unitNorm']['source'] == 'llm'
    close(c['qtyNorm']['variancePct'], -20)
    close(c['value'], 1500)                                           # $1.50/SF x 1,000 SF


def test_ai_plug_and_overrides():
    ai = {'Y': {'value': 444.0, 'unit_price': None, 'confidence': 'medium'}}
    r = by(engine.level(ITEMS, FIELD, {'ai_auto': True}, None, ai))
    assert r['A']['cells']['Y']['plug']['method'] == 'ai_estimate' and r['A']['cells']['Y']['value'] == 444.0
    low = {'Y': {'value': 444.0, 'confidence': 'low'}}
    assert by(engine.level(ITEMS, FIELD, {'ai_auto': True}, None, low))['A']['cells']['Y']['plug']['method'] == 'average_of_bidders'
    ov = [{'bidder_id': 'A', 'item_key': 'Y', 'action': 'manual_value', 'payload': {'value': 77}},
          {'bidder_id': 'C', 'item_key': 'Y', 'action': 'plug', 'payload': {'method': 'gc_estimate'}}]
    r = by(engine.level(ITEMS, FIELD, None, ov))
    assert r['A']['cells']['Y']['state'] == 'priced' and r['A']['cells']['Y']['value'] == 77
    assert r['C']['cells']['Y']['state'] == 'plugged' and r['C']['cells']['Y']['value'] == 500


def test_totals_and_extras():
    b = bidder('E', 1000, 1.0, 20.0)
    b['extras'] = [{'description': 'Mobilization', 'amount': 100.0, 'treatment': 'add'}, {'description': 'Tax credit', 'amount': 30.0, 'treatment': 'credit'},
                   {'description': 'Alternate', 'amount': 999.0, 'treatment': 'alternate'}]
    r = by(engine.level(ITEMS, [b], {'allowances': [{'name': 'Allowance', 'amount': 50}]}))['E']
    close(r['asBid'], 1000 + 20 + 100 - 30)
    close(r['plugs'], 50)
    close(r['leveledTotal'], 1140)
    close(r['scopePriced'], 1.0)


def test_policy_weights_normalize_to_100():
    pol = policy_mod.normalize({'criteria': [{'id': 'a', 'ordinal': 2, 'name': 'A', 'weight': 30, 'kind': 'qualitative', 'scale': []},
                                             {'id': 'p', 'ordinal': 1, 'name': 'Price', 'weight': 90, 'kind': 'price', 'scale': []}], 'gates': []})
    assert [c['id'] for c in pol['criteria']] == ['p', 'a']
    close(sum(c['weight'] for c in pol['criteria']), 100, 0.05)


def test_scoring_gates_and_rank():
    pol = policy_mod.normalize({'criteria': [
        {'id': 'price', 'ordinal': 1, 'name': 'Price', 'weight': 60, 'kind': 'price', 'scale': []},
        {'id': 'scope', 'ordinal': 2, 'name': 'Scope', 'weight': 20, 'kind': 'scope_completeness', 'scale': []},
        {'id': 'war', 'ordinal': 3, 'name': 'Warranty', 'weight': 20, 'kind': 'qualitative',
         'scale': [{'level': 1, 'label': 'Exceeds', 'points': 100, 'definition': ''}, {'level': 2, 'label': 'Meets', 'points': 70, 'definition': ''}, {'level': 3, 'label': 'Below', 'points': 0, 'definition': ''}]}],
        'gates': [{'id': 'g', 'name': 'Scope priced', 'rule': '', 'check': 'scope_priced_min_pct', 'threshold': 90, 'severity': 'disqualify'}]})
    bs = engine.level(ITEMS, [bidder('Cheap', 1000, 0.5, None), bidder('Mid', 1000, 1.0, 20.0), bidder('High', 1000, 1.2, 25.0)])['bidders']
    rated = {'Cheap': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 1, 'justification': 'x'}]},
             'Mid': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 1, 'justification': 'x'}]},
             'High': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 3, 'justification': 'x'}]}}
    rec = assess.score(pol, bs, rated, {})
    b = {x['id']: x for x in bs}
    assert b['Cheap']['qualified'] is False and b['Cheap']['band'] == 'not_qualified'   # excluded Y: 80% of scope priced
    assert rec == 'Mid' and b['Mid']['rank'] == 1 and b['High']['rank'] == 2
    close(b['Mid']['score'], 60 + 20 + 20, 0.05)
    close(b['High']['score'], 60 * 1020 / 1225 + 20 + 0, 0.06)


def test_reconcile_counts_lines_the_stated_total_includes():
    from wyre_level.pipeline import extract
    ext = {'stated_total': 1250.0, 'cells': {'A': {'status': 'priced', 'amount': 1000.0}},
           'extra_lines': [{'description': 'Winter protection allowance', 'amount': 250.0, 'treatment': 'allowance'},
                           {'description': 'Alternate 9', 'amount': 400.0, 'treatment': 'alternate'}]}
    extract.reconcile(ext)
    assert ext['extra_lines'][0]['treatment'] == 'add' and ext['extra_lines'][1]['treatment'] == 'alternate'
    assert ext['lines_total'] == 1250.0 and ext['checks'] == []
    ext2 = {'stated_total': 1300.0, 'cells': {'A': {'status': 'priced', 'amount': 1000.0}},
            'extra_lines': [{'description': 'Allowance', 'amount': 250.0, 'treatment': 'allowance'}]}
    extract.reconcile(ext2)                                   # does not add up either way: left alone and flagged
    assert ext2['extra_lines'][0]['treatment'] == 'allowance' and len(ext2['checks']) == 1


def test_award_rule_lowest_price_with_best_value_window():
    base = {'criteria': [
        {'id': 'price', 'ordinal': 1, 'name': 'Price', 'weight': 60, 'kind': 'price', 'scale': []},
        {'id': 'war', 'ordinal': 2, 'name': 'Warranty', 'weight': 40, 'kind': 'qualitative',
         'scale': [{'level': 1, 'label': 'Meets', 'points': 100, 'definition': ''}, {'level': 2, 'label': 'Short', 'points': 0, 'definition': ''}]}], 'gates': []}
    field = [bidder('Low', 1000, 1.0, 20.0), bidder('Near', 1000, 1.02, 20.0), bidder('Far', 1000, 1.10, 20.0)]
    rated = {'Low': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 2, 'justification': ''}]},
             'Near': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 1, 'justification': ''}]},
             'Far': {'gates': [], 'ratings': [{'criterion_id': 'war', 'level': 1, 'justification': ''}]}}
    def pick(rule):
        pol = policy_mod.normalize(dict(base, criteria=[dict(c) for c in base['criteria']], award_rule=rule))
        return assess.score(pol, engine.level(ITEMS, field)['bidders'], rated, {})
    assert pick({'basis': 'highest_score'}) == 'Near'                              # warranty outweighs a 2% price gap
    assert pick({'basis': 'lowest_price', 'best_value_window_pct': None}) == 'Low'  # strict lowest price
    assert pick({'basis': 'lowest_price', 'best_value_window_pct': 3}) == 'Near'    # within the 3% window, best score wins
    assert pick({'basis': 'lowest_price', 'best_value_window_pct': 1}) == 'Low'     # 2% is outside a 1% window
