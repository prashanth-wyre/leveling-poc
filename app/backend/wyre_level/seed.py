"""Seed the database from the sample sets in samples/, plus a generated 50-bidder package for scale testing."""
import json
import math
import random
import shutil

import yaml

from . import config, db, ingest
from .pipeline import run as runner

SECTIONS = {
    '07.50': {'Roof assemblies': ['RA1', 'RA2'], 'Sheet metal and accessories': ['FLASH', 'ELD', 'FLUTE', 'TRANS']},
    '09.67': {'Concrete finishes': ['PSC1', 'SC1', 'SC2', 'SC4'], 'Resinous flooring and coatings': ['RN1', 'RN2', 'TC1'], 'General': ['MOIST', 'TOP']},
    '32.90': {'Site furnishings': ['FLAG', 'BENCH47', 'BIKE'], 'Planting': ['SILVA', 'TREES', 'SHRUBS', 'GRASS', 'MMULCH', 'WMULCH', 'SOD'],
              'Irrigation': ['IRRIG', 'SLEEVE'], 'Paving': ['PAVERS'], 'General': ['FENCE', 'DRAIN', 'MAINT']},
}
PACKAGES = [('07.50', '07.50_roofing', 'Roofing'), ('09.67', '09.67_fluid_flooring', 'Fluid-Applied Flooring'), ('32.90', '32.90_landscaping', 'Landscaping and Irrigation')]


def kind_of(filename):
    n = filename.lower()
    if 'awarding_policy' in n or 'award' in n and 'policy' in n:
        return 'award_policy'
    if 'plugging_policy' in n or 'unit_conversions' in n:
        return 'plug_policy'
    if 'scope_sheet' in n or 'scope sheet' in n:
        return 'scope_sheet'
    if any(w in n for w in ('prequal', 'clarification', 'brief')):
        return 'supporting'
    return 'bid'


def add_document(package_id, src, kind=None, t=None):
    did = db.new_id('d_')
    dest = config.UPLOADS / did
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy(src, dest / src.name)
    db.insert('documents', id=did, package_id=package_id, kind=kind or kind_of(src.name), filename=src.name, path=str(dest / src.name),
              mime=ingest.mime_of(src.name), size=src.stat().st_size, uploaded_at=t or db.now(), status='uploaded', error=None, extraction=None)
    return did


def settings_from_yaml(y, code):
    """Map samples/tcjc_plugging/gc/plugging_policy.yaml onto engine settings."""
    def m(x):
        return 'ai_estimate' if x == 'ai_market_price' else x

    def rule(r):
        out = {k: v for k, v in r.items() if k in ('amount', 'rate_source', 'min_pool')}
        out['method'] = m(r['method'])
        if 'fallback' in r:
            out['fallback'] = [({**s, 'method': m(s['method'])} if isinstance(s, dict) else m(s)) for s in r['fallback']]
        return out
    pk, d = y['packages'][code], y['defaults']
    return {
        'threshold_pct': y['quantity_normalization']['threshold_pct'], 'ai_auto': False, 'ai_web_search': True, 'ai_text': True,
        'default': {'method': m(d['method']), 'fallback': [m(x) for x in d['fallback']], 'min_pool': d['comparable_pool']['min_pool'],
                    'outlier_trim_pct': d['comparable_pool']['outlier_trim_pct'], 'outlier_trim_min_pool': d['comparable_pool']['outlier_trim_min_pool']},
        'items': {k: rule(r) for k, r in pk['items'].items()},
        'allowances': pk.get('allowances_all_bidders') or [],
    }, pk.get('manual_overrides') or []


def seed_scenario_set():
    root = config.SAMPLES / 'tcjc_plugging'
    pid = db.new_id('p_')
    db.insert('projects', id=pid, name='Teton County Justice Center', location='Jackson, Wyoming', created_at=db.now())
    y = yaml.safe_load((root / 'gc' / 'plugging_policy.yaml').read_text())
    t = db.now()
    for code, slug, name in PACKAGES:
        key = json.loads((root / 'answer_key' / f'{slug}.json').read_text())
        sec_of = {k: s for s, ks in SECTIONS[code].items() for k in ks}
        order = [k for ks in SECTIONS[code].values() for k in ks]
        by = {i['key']: i for i in key['gc_items']}
        items = [{'key': k, 'name': by[k]['desc'], 'section': sec_of[k], 'unit': by[k]['unit'], 'qty': by[k]['qty'], 'rate': by[k]['rate'],
                  'estimate': by[k]['estimate'], 'depth': by[k]['depth'], 'spec': None} for k in order]
        settings, manual = settings_from_yaml(y, code)
        kid = db.new_id('k_')
        db.insert('packages', id=kid, project_id=pid, code=code, name=name, created_at=db.now(), scope={'items': items}, policy=None,
                  settings=settings, result=None, run=None, last_leveled_at=None)
        for f in sorted((root / 'bids' / slug).iterdir()):
            t += 1
            add_document(kid, f, 'bid', t)
        for f in [root / 'gc' / 'awarding_policy.md', root / 'gc' / 'plugging_policy.yaml', root / 'gc' / 'subcontractor_prequal.xlsx',
                  root / 'gc' / 'project_brief.md', root / 'gc' / slug / 'scope_sheet.xlsx']:
            t += 1
            add_document(kid, f, None, t)
        for o in manual:
            db.insert('overrides', id=db.new_id('o_'), package_id=kid, bidder_id=runner.bidder_id(o['bidder']), item_key=o['item'], action='plug',
                      payload={'method': o['method'], 'amount': o['amount'], 'note': o['reason']}, created_at=db.now())
    return pid


def seed_workbook_set():
    root = config.SAMPLES / 'tcjc'
    pid = db.new_id('p_')
    db.insert('projects', id=pid, name='Teton County Justice Center (workbook bids)', location='Jackson, Wyoming', created_at=db.now() + 1)
    t = db.now()
    for code, slug, name in PACKAGES:
        kid = db.new_id('k_')
        db.insert('packages', id=kid, project_id=pid, code=code, name=name, created_at=db.now(), scope=None, policy=None,
                  settings={'ai_text': True}, result=None, run=None, last_leveled_at=None)
        for f in sorted((root / 'bids' / slug).iterdir()):
            t += 1
            add_document(kid, f, 'bid', t)
        for f in [root / 'gc' / 'awarding_policy.md', root / 'gc' / 'subcontractor_prequal.xlsx', root / 'gc' / 'bid_clarification_log.xlsx',
                  root / 'gc' / 'project_brief.md', root / 'gc' / slug / 'scope_sheet.xlsx']:
            t += 1
            add_document(kid, f, None, t)
    return pid


# ---------------------------------------------------------------- generated 50-bidder package
STEEL = [
    ('Structural framing', [('W-shape columns', 182000), ('Wide-flange beams and girders', 410000), ('HSS columns', 64000), ('Braced frame members', 118000),
                            ('Moment frame connections', 96000), ('Roof framing', 142000), ('Transfer girders', 88000), ('Base plates and anchor rods', 37000),
                            ('Embeds and bearing plates', 29000)]),
    ('Joists and deck', [('Open-web steel joists', 124000), ('Joist girders', 58000), ('3 in. composite floor deck', 136000, 'SF', 42000),
                         ('1-1/2 in. roof deck', 74000, 'SF', 30000), ('Low roof deck', 21000, 'SF', 8000), ('Deck closures and pour stops', 18000), ('Shear studs', 26000)]),
    ('Stairs and rails', [('Egress stair 1', 46000), ('Egress stair 2', 46000), ('Detention stair', 68000), ('Guardrails', 39000, 'LF', 600),
                          ('Handrails', 17000, 'LF', 400), ('Roof access ladder', 6500), ('Ship ladder and hatch frame', 9000)]),
    ('Miscellaneous metals', [('Lintels', 22000), ('Elevator pit ladder and sump frames', 7500), ('Elevator hoist beams', 12000), ('Bollards', 14000, 'EA', 14),
                              ('Canopy framing', 52000), ('Mechanical screen framing', 44000), ('Roof equipment supports', 31000), ('Sally port door frames', 27000),
                              ('Trench and area drain frames', 8000)]),
    ('Engineering and general', [('Shop drawings and connection design', 61000), ('BIM coordination', 24000), ('Shop primer', 33000), ('Galvanizing', 41000),
                                 ('Field touch-up', 9000), ('Mobilization and crane', 78000), ('Erection safety and deck protection', 28000),
                                 ('Field bolting and inspection support', 36000)]),
]
NAME_A = ['Ridgeline', 'Sawtooth', 'Bitterroot', 'Larkspur', 'Granite Basin', 'Yellowpine', 'Juniper Flat', 'Red Butte', 'Stillwater', 'Paintbrush', 'Lodgepole',
          'Antelope Draw', 'Cottonwood', 'Sagehen', 'Clearwater', 'Hoback', 'Snowmelt', 'Tamarack', 'Highline', 'Bluebird', 'Ironwood', 'Marmot Pass',
          'Greys River', 'Buffalo Fork', 'Wapiti', 'Shoshone', 'Arrowleaf']
NAME_B = ['Steel', 'Ironworks', 'Fabricators', 'Structural', 'Metals', 'Steel Erectors', 'Welding & Fab']


def seed_stress(n_bidders=50):
    r = random.Random(77120541)
    pid = db.new_id('p_')
    db.insert('projects', id=pid, name='Scale test (generated data)', location='Mountain West', created_at=db.now() + 2)
    items = []
    for sec, rows in STEEL:
        for row in rows:
            name, est = row[0], row[1]
            unit, qty = (row[2], row[3]) if len(row) > 2 else ('LS', None)
            items.append({'key': f'S{len(items) + 1:02d}', 'name': name, 'section': sec, 'unit': unit, 'qty': qty, 'rate': round(est / qty, 4) if qty else None,
                          'estimate': float(est), 'depth': None, 'spec': None})
    market = [it['estimate'] * math.exp(0.06 + 0.22 * r.gauss(0, 1)) for it in items]
    contest = [2.3 if x < 0.2 else 1 if x < 0.55 else 0.55 for x in (r.random() for _ in items)]
    secs = [s for s, _ in STEEL]
    kid = db.new_id('k_')
    policy = {
        'summary': 'Generated package with no policy document: price and scope completeness only, and one pass/fail rule on scope.',
        'criteria': [
            {'id': 'price', 'ordinal': 1, 'name': 'Leveled price', 'weight': 70.0, 'kind': 'price', 'description': 'Leveled total package value.',
             'how_scored': 'Lowest qualified leveled total scores 100; others in proportion.', 'source_clause': None, 'rationale': 'Set by the seed data.',
             'scale': [{'level': 1, 'label': 'Lowest', 'points': 100, 'definition': 'Lowest leveled total'}, {'level': 2, 'label': 'Within 10%', 'points': 90, 'definition': 'Within 10% of the lowest'},
                       {'level': 3, 'label': 'Over 10% above', 'points': 70, 'definition': 'More than 10% above the lowest'}]},
            {'id': 'scope', 'ordinal': 2, 'name': 'Scope completeness', 'weight': 30.0, 'kind': 'scope_completeness', 'description': 'Share of scope priced by the bidder.',
             'how_scored': 'Percent of scope by value priced by the bidder.', 'source_clause': None, 'rationale': 'Set by the seed data.',
             'scale': [{'level': 1, 'label': 'Complete', 'points': 100, 'definition': 'All scope priced'}, {'level': 2, 'label': 'Minor gaps', 'points': 80, 'definition': 'At least 90% priced'},
                       {'level': 3, 'label': 'Major gaps', 'points': 40, 'definition': 'Under 90% priced'}]}],
        'gates': [{'id': 'scope_min', 'name': 'Scope priced', 'rule': 'A bidder must price at least 90% of the scope by value.', 'check': 'scope_priced_min_pct',
                   'threshold': 90, 'severity': 'disqualify', 'source_clause': None}],
        'source': 'seed',
    }
    db.insert('packages', id=kid, project_id=pid, code='05.12', name=f'Structural Steel ({n_bidders} bidders)', created_at=db.now(), scope={'items': items},
              policy=policy, settings={'ai_text': False, 'threshold_pct': 5.0}, result=None, run=None, last_leveled_at=None)
    sh = runner.scope_hash(items)
    used, t = set(), db.now()
    arch = [('complete', 34), ('lowgaps', 15), ('high', 12), ('section', 10), ('folded', 11), ('spiky', 11), ('thin', 7)]
    for k in range(n_bidders):
        roll, acc, kind = r.random() * 100, 0, 'complete'
        for a, w in arch:
            acc += w
            if roll < acc:
                kind = a
                break
        L, sigma, gaps = math.exp(0.09 * r.gauss(0, 1)), 0.085, 0
        if kind == 'complete':
            gaps = 1 if r.random() < 0.35 else 0
        if kind == 'lowgaps':
            L, gaps = L * 0.87, 6 + r.randrange(6)
        if kind == 'high':
            L *= 1.17
        if kind == 'spiky':
            sigma = 0.2
        if kind == 'thin':
            L, gaps = L * 0.78, 8 + r.randrange(6)
        bias = {s: math.exp(0.07 * r.gauss(0, 1)) for s in secs}
        cells = {}
        for i, it in enumerate(items):
            v = round(market[i] * L * bias[it['section']] * math.exp(min(0.3, sigma * contest[i]) * max(-2, min(2, r.gauss(0, 1)))))
            c = {'scope_key': it['key'], 'status': 'priced', 'bid_description': it['name'], 'quantity': None, 'unit': None, 'unit_price': None, 'amount': float(v),
                 'confidence': 0.97, 'source_snippet': f"{it['name']} ... ${v:,}"}
            if it['qty']:                                    # some bidders quote decks in squares, and some assume more or less material
                q = it['qty'] * (1 + (r.choice([-1, 1]) * (0.06 + r.random() * 0.14) if r.random() < 0.25 else r.uniform(-0.03, 0.03)))
                if it['unit'] == 'SF' and r.random() < 0.3:
                    c.update(quantity=round(q / 100), unit='SQ', gc_units_per_bid_unit=100, conversion_explanation='1 roofing square = 100 SF')
                    c['unit_price'] = round(v / c['quantity'], 2)
                else:
                    c.update(quantity=round(q), unit=it['unit'])
                    c['unit_price'] = round(v / c['quantity'], 2)
                c['amount'] = round(c['quantity'] * c['unit_price'], 2)
            cells[it['key']] = c
        keys = [it['key'] for it in items]
        if kind == 'section':
            sec = r.choice([s for s in secs if s != 'Structural framing'])
            for it in items:
                if it['section'] == sec:
                    cells[it['key']] = {'scope_key': it['key'], 'status': 'excluded', 'confidence': 0.95, 'source_snippet': f'Excludes {sec.lower()}'}
        if kind == 'folded':
            for _ in range(2):
                sec = r.choice(secs)
                ks = sorted((k2 for k2 in keys if next(i for i in items if i['key'] == k2)['section'] == sec and cells[k2]['status'] == 'priced'), key=lambda k2: cells[k2]['amount'])
                if len(ks) >= 3:
                    host = ks[-1]
                    for k2 in ks[:1 + r.randrange(2)]:
                        cells[host]['amount'] = round(cells[host]['amount'] + cells[k2]['amount'], 2)
                        cells[host]['quantity'] = cells[host]['unit'] = cells[host]['unit_price'] = None
                        cells[k2] = {'scope_key': k2, 'status': 'included', 'confidence': 0.9, 'source_snippet': 'Included above'}
        g = 0
        while g < gaps:
            k2 = r.choice(keys)
            if cells[k2]['status'] == 'priced':
                cells[k2] = {'scope_key': k2, 'status': r.choice(['excluded', 'not_mentioned']), 'confidence': 0.9, 'source_snippet': None}
                g += 1
        tries = 0
        while True:
            nm = f'{NAME_A[(k * 7 + 3 + tries) % len(NAME_A)]} {NAME_B[(k * 3 + tries) % len(NAME_B)]}'
            tries += 1
            if nm not in used:
                used.add(nm)
                break
        total = round(sum(c['amount'] for c in cells.values() if c['status'] == 'priced'), 2)
        ext = {'doc_type': 'bid', 'bidder_name': nm, 'bid_date': '2026-11-10', 'reference': f'G-{1000 + k}', 'is_revision': False, 'stated_total': total,
               'items': list(cells.values()), 'cells': cells, 'extra_lines': [], 'inclusions': [], 'exclusions': [], 'clarifications': [], 'alternates': [],
               'warranty': ['Per contract documents'], 'validity_days': 60, 'addenda_acknowledged': ['Addendum 01'], 'tax': 'excluded', 'red_flags': [],
               'checks': [], 'lines_total': total, 'scope_hash': sh, 'synthetic': True}
        t += 1
        db.insert('documents', id=db.new_id('d_'), package_id=kid, kind='bid', filename=f'{k + 1:02d}_{nm.replace(" ", "_")}.xlsx', path=None, mime=ingest.mime_of('x.xlsx'),
                  size=0, uploaded_at=t, status='extracted', error=None, extraction=ext)
    return pid


TWENTY_NAME = 'Teton County Justice Center (20 bidders, complete scope)'


def seed_twenty():
    """samples/tcjc_20: three packages on their complete scope, 20 bidders each, with real documents to read."""
    root = config.SAMPLES / 'tcjc_20'
    if not root.exists():
        return None
    pid = db.new_id('p_')
    db.insert('projects', id=pid, name=TWENTY_NAME, location='Jackson, Wyoming', created_at=db.now() + 3)
    y = yaml.safe_load((root / 'gc' / 'plugging_policy.yaml').read_text())
    t = db.now()
    for kf in sorted((root / 'answer_key').glob('*.json')):
        key = json.loads(kf.read_text())
        code, slug = key['package'], kf.stem
        items = [{k: it.get(k) for k in ('key', 'name', 'section', 'unit', 'qty', 'rate', 'estimate', 'depth', 'spec')} for it in key['items']]
        settings, _ = settings_from_yaml(y, code)
        settings['ai_text'] = True
        kid = db.new_id('k_')
        db.insert('packages', id=kid, project_id=pid, code=code, name=key['name'], created_at=db.now(), scope={'items': items}, policy=None,
                  settings=settings, result=None, run=None, last_leveled_at=None)
        for f in sorted((root / 'bids' / slug).iterdir()):
            t += 1
            add_document(kid, f, 'bid', t)
        for f in [root / 'gc' / 'awarding_policy.md', root / 'gc' / 'plugging_policy.yaml', root / 'gc' / 'subcontractor_prequal.xlsx',
                  root / 'gc' / 'bid_clarification_log.xlsx', root / 'gc' / 'project_brief.md', root / 'gc' / slug / 'scope_sheet.xlsx']:
            t += 1
            add_document(kid, f, None, t)
    return pid


SEEDERS = [('Teton County Justice Center', seed_scenario_set), ('Teton County Justice Center (workbook bids)', seed_workbook_set),
           ('Scale test (generated data)', seed_stress), (TWENTY_NAME, seed_twenty)]


def seed(reset=False):
    if reset:
        for tbl in ('overrides', 'documents', 'packages', 'projects'):
            db.conn().execute(f'DELETE FROM {tbl}')
        db.conn().commit()
        shutil.rmtree(config.UPLOADS, ignore_errors=True)
        config.UPLOADS.mkdir(parents=True, exist_ok=True)
    added = False
    for name, fn in SEEDERS:              # each sample project is added once; existing ones are left alone
        if not db.one('SELECT id FROM projects WHERE name=?', (name,)):
            added = bool(fn()) or added
    return added


if __name__ == '__main__':
    import sys
    print('seeded' if seed(reset='--reset' in sys.argv) else 'already seeded (use --reset to start over)')
