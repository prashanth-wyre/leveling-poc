"""Sample set 3: twenty subcontractors per bid package, on the complete scope of each package.

    uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml \
        tools/gen_samples/twenty.py

Writes samples/tcjc_20/. The scope of each package is every line on its TCJC workbook tab that the GC estimated or
that two or more real bidders priced; prices start from the real workbook figures for each line. Bidders, their
pricing patterns, documents and all qualification facts are SYNTHETIC. The answer key is the leveling engine
(app/backend/wyre_level/engine.py) run on the true contents of every document.
"""
import json
import math
import random
import re
import shutil
import statistics
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / 'app' / 'backend'))

import yaml  # noqa: E402
from openpyxl import Workbook as XWorkbook  # noqa: E402
from openpyxl.styles import Font, PatternFill  # noqa: E402

import gc_docs  # noqa: E402
import verify  # noqa: E402
from model import load_package  # noqa: E402
from render_office import render_docx, render_xlsx  # noqa: E402
from render_pdf import render_pdf  # noqa: E402
from specs import PACKAGES as BASE_PACKAGES  # noqa: E402
from tcjc import Workbook, shift  # noqa: E402
from wyre_level import engine  # noqa: E402

SRC = ROOT / 'data' / 'TCJC_CD_Estimate Summary_251211.xlsm'
OUT = ROOT / 'samples' / 'tcjc_20'
RENDER = {'pdf': render_pdf, 'docx': render_docx, 'xlsx': render_xlsx}
N_BIDDERS = 20
SETTINGS = {'threshold_pct': 5.0, 'default': {'method': 'average_of_bidders', 'fallback': ['gc_estimate'], 'min_pool': 2,
                                              'outlier_trim_pct': 50, 'outlier_trim_min_pool': 3}, 'items': {}, 'allowances': []}
SKIP = re.compile(r'contingency|textura|quantity miss|quantity check|extra money|additional tax|add alternate|add option|price to add', re.I)

SETS = {
    '32.90': dict(sheet='32.90', slug='32.90_landscaping', name='Landscaping and Irrigation', est_block='AC', prefix='LA', area='307', seed=3290,
                  suffixes=['Landscape Co.', 'Landscapes', 'Nursery & Landscape', 'Grounds', 'Outdoor Works', 'Turf & Irrigation', 'Gardens', 'Site & Landscape'],
                  headers={'Site Furnishings': 'Site furnishings', 'Landscape': 'Planting', 'Irrigation System': 'Irrigation',
                           'Paving and Surfacing': 'Paving', 'General': 'General'},
                  alternate='Alternate #7: Hot water and irrigation submetering connected to BAS (irrigation work)',
                  warranty_min=BASE_PACKAGES['32.90']['warranty_min'],
                  warranty_ok=['1-year plant replacement warranty from Substantial Completion, no exclusions', '1-year irrigation warranty including first winterization and spring start-up',
                               '2-year warranty on unit pavers', "Manufacturer's standard warranty on site furnishings (3 years)"],
                  warranty_short=['90-day plant warranty, excluding winter kill', '1-year irrigation warranty', '1-year warranty on pavers']),
    '33.00': dict(sheet='33.00', slug='33.00_site_utilities', name='Site Utilities', est_block='AM', prefix='SU', area='208', seed=3300,
                  suffixes=['Excavation', 'Earthworks', 'Utilities', 'Underground', 'Pipeline Co.', 'Civil Constructors', 'Dirt Works', 'Trenching'],
                  sections=[('Demolition', r'^demo'), ('Storm drainage', r'storm|trench drain|planter drain'), ('Sanitary and water', r'sanitary|water service'),
                            ('Electrical trenching', r'electrical'), ('General', r'.')],
                  alternate='Alternate #9: Snow melt system deduct (utility work in the snow melt areas)',
                  warranty_min=[('Underground piping, structures and connections', '1-year workmanship warranty from Substantial Completion, including repair of settlement'),
                                ('Trench restoration and patch back', '1-year warranty against settlement and cracking')],
                  warranty_ok=['1-year workmanship warranty from Substantial Completion, including settlement repair', '1-year warranty on trench restoration and patch back'],
                  warranty_short=['90-day workmanship warranty', 'Patch back warranted for 6 months']),
    '32.13': dict(sheet='32.13', slug='32.13_concrete_paving', name='Rigid Paving (Concrete Paving)', est_block='AC', prefix='CP', area='406', seed=3213,
                  suffixes=['Concrete', 'Flatwork', 'Concrete Constructors', 'Paving', 'Cement Works', 'Site Concrete', 'Concrete & Curb'],
                  sections=[('Curbs and flatwork', r'curb|sidewalk|driveway|ada|stairs|eco pan|insulation'), ('Walls and edges', r'wall|mowband|edge restraint'),
                            ('Pads and foundations', r'base for|pad|foundation|bollard'), ('General', r'.')],
                  alternate='Alternate #10: Snow melt system add (concrete paving over snow melt areas)',
                  warranty_min=[('Concrete paving, curbs and site walls', '1-year warranty against cracking beyond tolerance, scaling and settlement'),
                                ('Sealants and joint fillers', '2-year warranty')],
                  warranty_ok=['1-year warranty against cracking beyond tolerance, scaling and settlement', '2-year warranty on sealants and joint fillers'],
                  warranty_short=['Workmanship warranted for 1 year; cracking and scaling excluded', '1-year warranty on sealants']),
}

PLACES = ['Absaroka', 'Bridger Ridge', 'Gros Ventre', 'Hoback', 'Palisades', 'Granite Creek', 'Cache Creek', 'Fall Creek', 'Flat Creek', 'Spring Gulch',
          'Moose Creek', 'Signal Mountain', 'Shadow Mountain', 'Two Ocean', 'Togwotee', 'Blacktail', 'Buffalo Valley', 'Pacific Creek', 'Ditch Creek',
          'Lupine Meadow', 'Taggart', 'Bradley Lake', 'Phelps Lake', 'Cascade Canyon', 'Rendezvous', 'Mormon Row', 'Teton Pass', 'Fish Creek', 'Game Creek',
          'Horse Creek', 'Willow Creek', 'Cottonwood Creek', 'Antelope Flats', 'Sheep Mountain', 'Static Peak', 'Mount Leidy', 'Gravel Peak', 'Crystal Butte',
          'Coal Creek', 'Mosquito Creek', 'Red Hills', 'Slide Lake', 'Turpin Meadow', 'Lost Creek', 'Granite Ridge', 'Glory Bowl', 'Blue Miner', 'Avalanche Canyon',
          'Holly Lake', 'Surprise Lake', 'Garnet Canyon', 'Hanging Canyon', 'Moran Bay', 'Leigh Lake', 'Bivouac Peak', 'Eagles Rest', 'Doane Peak', 'Ranger Peak',
          'Owl Peak', 'Thor Peak', 'Rockchuck', 'Housetop', 'Fossil Mountain', 'Battleship', 'Wall Creek', 'Spread Creek', 'Lozier Hill', 'Breccia Peak',
          'Brooks Lake', 'Pilot Knob', 'Tripod Peak', 'Mail Cabin']
PDF_FONTS = ['Helvetica', 'Times-Roman', 'Courier']
OFFICE_FONTS = ['Calibri', 'Arial', 'Georgia', 'Cambria']
ACCENTS = ['1F3864', '7A1F1F', '1B5E20', '263238', '0D47A1', '4E342E', '00695C', 'BF360C', '33691E', '5D4037', '37474F', '6A1B9A']
LAYOUTS = [('pdf', 'proposal'), ('pdf', 'quote'), ('docx', 'letter'), ('docx', 'short'), ('xlsx', 'bidform'), ('xlsx', 'estimate')]


def r2(x):
    return round(x + 1e-9, 2)


def slugify(s):
    return re.sub(r'[^a-z0-9]+', '-', s.lower()).strip('-')


# ---------------------------------------------------------------- the complete scope of a package, from its workbook tab
def complete_scope(code, pkg, rng):
    spec, t, k, eb = SETS[code], pkg['tab'], pkg['k'], pkg['est_block']
    start = next(r for r in t.rows if r > 11 and (t.text('B', r) or '').startswith('00-Base Bid - 90'))
    real = [b for b, _ in pkg['bidders'] if t.money(shift(b, 4), k['base'])]
    items, extras, sec = [], [], None
    for r in t.rows:
        if r <= start or r >= k['base']:
            continue
        name = ' '.join((t.text('C', r) or '').split())
        if not name:
            continue
        if 'headers' in spec and t.num('B', r) is None and name in spec['headers']:
            sec = spec['headers'][name]
            continue
        if SKIP.search(name):
            continue
        nums = [v for v in (t.money(shift(b, 4), r) for b in real) if v and v > 0]
        gq, gu = t.num(shift(eb, 1), r), t.text(shift(eb, 2), r)
        if len(nums) < 2 and not (gq and nums):
            if len(nums) == 1:
                extras.append({'name': name, 'value': nums[0]})
            continue
        if 'sections' in spec:
            sec = next(s for s, pat in spec['sections'] if re.search(pat, name, re.I))
        qty = unit = None
        if gq and gu:
            qty, unit = gq, gu
        else:
            seen = [(t.num(shift(b, 1), r), t.text(shift(b, 2), r)) for b in real]
            seen = [(q, u) for q, u in seen if q]
            if seen:
                q, u = max(seen, key=lambda x: sum(1 for y in seen if y[0] == x[0]))
                if not u and re.search(r'tree|shrub|grass|bench|stool|rack|receptacle|pole', name, re.I):
                    u = 'EA'
                if u:
                    qty, unit = q, u
        unit = engine.norm_unit(unit) if unit else 'LS'
        unit = {'MN': 'MO', 'MONTH': 'MO', 'MONTHS': 'MO'}.get(unit, unit)
        if unit == 'LS':
            qty = None
        market = statistics.median(nums)
        est = r2(market * math.exp(rng.gauss(0, 0.12)))
        items.append({'key': f"{spec['prefix']}{len(items) + 1:02d}", 'name': name, 'section': sec or 'General', 'unit': unit, 'qty': qty,
                      'rate': round(est / qty, 4) if qty else None, 'estimate': est, 'depth': 3.0 if 'mulch' in name.lower() else None,
                      'spec': None, 'market': market, 'row': r, 'real_values': nums})
    # group items by section (first appearance order) and number them in that order
    order = list(dict.fromkeys(i['section'] for i in items))
    items.sort(key=lambda i: (order.index(i['section']), i['row']))
    for n, i in enumerate(items, 1):
        i['key'] = f"{spec['prefix']}{n:02d}"
    return items, extras


# ---------------------------------------------------------------- how a bidder quotes one line
def quote_unit(item, rng, allow):
    """(bid unit, GC units per bid unit, stated depth, wording note, model-only conversion?) for a quantity line."""
    u, name = item['unit'], item['name'].lower()
    x = rng.random()
    if not allow:
        return u, 1.0, None, None, False
    if 'cobble' in name and x < 0.30:
        return 'TON', 60.0, None, '1 ton covers about 60 SF at 3 in. depth', True
    if name.startswith('storm line') and x < 0.30:
        return 'JT', 20.0, None, '20 ft pipe joints', True
    if 'mulch' in name and u == 'SF':
        if x < 0.22:
            return 'CY', engine.table_factor('CY', 'SF', 3, 3)[0], 3.0, 'priced by the cubic yard at 3 in. depth', False
        if x < 0.38:
            return 'SF', engine.table_factor('SF', 'SF', 2, 3)[0], 2.0, '2 in. depth', False
    if 'mulch' in name and u == 'CY' and x < 0.25:
        return 'SF', engine.table_factor('SF', 'CY', 3, 3)[0], 3.0, 'priced by the square foot at 3 in. depth', False
    if 'sidewalk' in name and u == 'SF':
        if x < 0.18:
            return 'CY', engine.table_factor('CY', 'SF', 6, None)[0], 6.0, '6 in. slab, priced per cubic yard of concrete', False
        if x < 0.38:
            return 'SY', 9.0, None, None, False
    if u == 'SF' and x < 0.18:
        return 'SY', 9.0, None, None, False
    if u == 'LF' and x < 0.12:
        return 'M', engine.table_factor('M', 'LF')[0], None, None, False
    if u == 'CY' and x < 0.22:
        return 'M3', engine.table_factor('M3', 'CY')[0], None, None, False
    return u, 1.0, None, None, False


def wording(name, style):
    plain = re.sub(r'^\d+(\.\d+)?\s*[-–]\s*', '', name)
    return {'code': name, 'plain': plain[:1].upper() + plain[1:], 'upper': plain.upper(), 'lower': plain[:1].upper() + plain[1:].lower()}[style]


def make_bidders(code, items, extras_tpl, rng, used_names):
    spec = SETS[code]
    arch = ['complete'] * 8 + ['lowgaps'] * 3 + ['high'] * 2 + ['section'] * 2 + ['folded'] * 2 + ['lumpsum', 'spiky', 'revision']
    rng.shuffle(arch)
    layouts = [LAYOUTS[i % len(LAYOUTS)] for i in range(N_BIDDERS)]
    rng.shuffle(layouts)
    total_market = sum(i['market'] for i in items)
    contest = {i['key']: (2.2 if x < 0.2 else 1.0 if x < 0.6 else 0.55) for i, x in ((i, rng.random()) for i in items)}
    secs = sorted({i['section'] for i in items})
    bidders = []
    for n in range(N_BIDDERS):
        a = arch[n]
        while True:                                     # one place name per firm across all packages, so no two bidders look alike
            place = rng.choice(PLACES)
            if not any(u.startswith(place + ' ') for u in used_names):
                name = f"{place} {rng.choice(spec['suffixes'])}"
                used_names.add(name)
                break
        fmt, layout = layouts[n]
        if a == 'lumpsum' and layout in ('bidform', 'short'):
            fmt, layout = 'xlsx', 'estimate'
        L = math.exp(0.085 * rng.gauss(0, 1)) * {'lowgaps': 0.9, 'high': 1.15}.get(a, 1.0)
        sigma = 0.2 if a == 'spiky' else 0.08
        bias = {s: math.exp(0.06 * rng.gauss(0, 1)) for s in secs}
        value = {i['key']: i['market'] * L * bias[i['section']] * math.exp(min(0.3, sigma * contest[i['key']]) * max(-2, min(2, rng.gauss(0, 1)))) for i in items}
        if a == 'spiky':
            small = [i['key'] for i in items if i['market'] / total_market < 0.08]
            for key in rng.sample(small, min(2, len(small))):
                value[key] *= rng.choice([2.1, 0.48])
        status = {i['key']: 'priced' for i in items}
        if a == 'complete' and rng.random() < 0.3:
            status[rng.choice([i['key'] for i in items if i['market'] / total_market < 0.06])] = 'not_mentioned'
        if a == 'lowgaps':
            for key in rng.sample([i['key'] for i in items if i['market'] / total_market < 0.1], rng.randint(2, 4)):
                status[key] = rng.choice(['excluded', 'not_mentioned'])
        if a == 'section':
            cand = [s for s in secs if 2 <= sum(1 for i in items if i['section'] == s) and sum(i['market'] for i in items if i['section'] == s) / total_market < 0.3]
            gone = rng.choice(cand)
            for i in items:
                if i['section'] == gone:
                    status[i['key']] = 'excluded'
        fold = {}
        if a == 'folded':
            for s in rng.sample(secs, len(secs)):
                ks = [i['key'] for i in items if i['section'] == s and status[i['key']] == 'priced']
                if len(ks) >= 3 and len(fold) < 2:
                    host = max(ks, key=lambda x: value[x])
                    for key in rng.sample([x for x in ks if x != host], 1 if fold else rng.randint(1, 2)):
                        fold[key] = host
            for key, host in fold.items():
                value[host] += value[key]
                status[key] = 'included'
        bidders.append({'n': n, 'company': name, 'arch': a, 'fmt': fmt, 'layout': layout, 'value': value, 'status': status, 'fold': fold,
                        'style': rng.choice(['code', 'plain', 'plain', 'upper', 'lower']), 'mix_ls': a != 'lumpsum' and rng.random() < 0.35})
    # bidder-added lines, credits, alternates and one arithmetic slip per package
    pool = [b for b in bidders if b['arch'] != 'revision']
    for b in rng.sample(pool, 6):
        tpl = rng.choice(extras_tpl) if extras_tpl and rng.random() < 0.6 else None
        if tpl:
            b.setdefault('extras', []).append({'description': tpl['name'], 'amount': r2(round(tpl['value'] * rng.uniform(0.8, 1.2), -1)), 'treatment': 'add'})
        else:
            pick = rng.choice(['Mobilization and demobilization', 'Payment and performance bond (1.1%)', 'Winter protection allowance'])
            base = sum(v for k, v in b['value'].items() if b['status'][k] == 'priced')
            amt = base * 0.011 if 'bond' in pick else base * rng.uniform(0.008, 0.02)
            b.setdefault('extras', []).append({'description': pick, 'amount': r2(round(amt, 0)), 'treatment': 'add'})
    for b in rng.sample([x for x in pool if not x.get('extras')], 2):
        base = sum(v for k, v in b['value'].items() if b['status'][k] == 'priced')
        b.setdefault('extras', []).append({'description': 'Less: sales tax on materials (project is tax exempt)', 'amount': r2(round(base * rng.uniform(0.015, 0.025), 0)), 'treatment': 'credit'})
        b['tax'] = 'credit'
    others = [x for x in pool if not x.get('tax')]
    for x in rng.sample(others, 2):
        x['tax'] = 'included'
    for x in rng.sample([x for x in others if not x.get('tax')], 2):
        x['tax'] = 'silent'
    for b in rng.sample(pool, 5):
        b['alts'] = [{'desc': spec['alternate'], 'amt': float(round(total_market * rng.uniform(0.02, 0.05), -2))}]
    slip = rng.choice([b for b in bidders if b['arch'] == 'complete' and b['layout'] in ('short', 'bidform', 'letter')] or [b for b in bidders if b['arch'] == 'complete'])
    slip['slip'] = True
    return bidders


def build_lines(b, items, rng, price_factor=1.0):
    """The lines exactly as they will be written in the document, plus the true reading of each baseline item."""
    by = {i['key']: i for i in items}
    lines, truth = [], {}
    for it in items:
        k, st = it['key'], b['status'][it['key']]
        desc = wording(it['name'], b['style'])
        if st == 'not_mentioned':
            truth[k] = {'status': 'not_mentioned'}
            continue
        if st == 'excluded':
            truth[k] = {'status': 'excluded'}
            if rng.random() < 0.5:
                lines.append({'desc': desc, 'qty': None, 'unit': None, 'up': None, 'amt': rng.choice(['Excluded', 'By others', 'NIC']), 'sec': it['section']})
            continue
        if st == 'included':
            host = wording(by[b['fold'][k]]['name'], b['style'])
            truth[k] = {'status': 'included'}
            lines.append({'desc': f"{desc} (included in {host})", 'qty': None, 'unit': None, 'up': None, 'amt': rng.choice(['Included', 'Incl.', 'Included above']), 'sec': it['section']})
            continue
        v = b['value'][k] * price_factor
        host_of_fold = k in b['fold'].values()
        as_ls = b['arch'] == 'lumpsum' or not it['qty'] or host_of_fold or (b['mix_ls'] and rng.random() < 0.25)
        if as_ls:
            amt = float(round(v, 0))
            lines.append({'desc': desc, 'qty': None, 'unit': None, 'up': None, 'amt': amt, 'sec': it['section']})
            truth[k] = {'status': 'priced', 'quantity': None, 'unit': None, 'unit_price': None, 'amount': amt}
            continue
        unit, factor, depth, note, model_only = quote_unit(it, rng, allow=True)
        x = rng.random()
        var = rng.uniform(-0.03, 0.03) if x < 0.78 else rng.choice([-1, 1]) * rng.uniform(0.06, 0.18)
        q_gc = it['qty'] * (1 + var)
        q = q_gc / factor
        if it['unit'] == 'EA' and unit == 'EA':
            q = max(1, round(it['qty'] * (1 + var)))
        else:
            q = round(q) if q >= 20 else round(q, 1)
        q = q or 1
        up = r2(v / it['qty'] * factor)
        amt = r2(q * up)
        if b.get('slip') and not b.get('slipped'):
            amt = r2(amt + rng.choice([900, -450, 1350, 2700]))
            b['slipped'] = {'item': k, 'correct': r2(q * up), 'written': amt}
        lines.append({'desc': desc + (f' ({note})' if note else ''), 'qty': float(q), 'unit': unit, 'up': up, 'amt': amt, 'sec': it['section']})
        truth[k] = {'status': 'priced', 'quantity': float(q), 'unit': unit, 'unit_price': up, 'amount': amt, 'depth_in': depth,
                    'gc_units_per_bid_unit': factor if model_only else None, 'model_only_conversion': model_only}
    for e in b.get('extras', []):
        amt = -abs(e['amount']) if e['treatment'] == 'credit' else e['amount']
        lines.append({'desc': e['description'], 'qty': None, 'unit': None, 'up': None, 'amt': float(amt), 'sec': 'Additional items'})
    return lines, truth


INTRO = {
    'proposal': '{c} is pleased to submit this proposal for Bid Package {code} {pkg} at the Teton County Justice Center, per the 90% Construction Documents and the scope sheet.',
    'quote': 'Quote for {pkg} at the Teton County Justice Center per plans and specifications.',
    'letter': 'Thank you for the opportunity to bid. {c} offers the following price for the {pkg} package.',
    'short': 'Pricing for {pkg} at the Justice Center.',
    'bidform': 'Bid Form - Bid Package {code} {pkg}',
    'estimate': 'Estimate - {pkg}',
}


def render_bid(code, b, lines, rng, out_dir, superseded=False):
    spec = SETS[code]
    total = r2(sum(l['amt'] for l in lines if isinstance(l['amt'], float)))
    excl = [wording(i, b['style']) for i in b.get('excluded_names', [])]
    q = b['qual']
    when = date(2025, 11, 11) if superseded else date(2025, 11, rng.choice([14, 17, 17, 18, 18, 18]))
    intro = INTRO[b['layout']].format(c=b['company'], code=code, pkg=spec['name'])
    if b['arch'] == 'revision' and not superseded:
        intro = 'REVISED BID - supersedes our quote dated 11/11/2025. ' + intro
    if superseded:
        intro = 'Budget quote. A final price will follow.'
    clar = []
    if q['addenda_missing']:
        clar.append('Pricing is based on the 90% Construction Documents dated 10/27/2025. Addendum 01 was not received and is not included.')
    if b['arch'] == 'lumpsum':
        clar.append('Lump sum pricing only; quantities are not provided.')
    if any(t.get('model_only_conversion') for t in b['truth'].values()):
        clar.append('Some items are priced in our own units; the unit and its coverage are stated on each line.')
    tax = {'credit': 'silent', 'included': 'included', 'silent': 'silent'}.get(b.get('tax'), 'excluded')
    fmt, layout = ('pdf', 'quote') if superseded else (b['fmt'], b['layout'])
    font = rng.choice(PDF_FONTS) if fmt == 'pdf' else rng.choice(OFFICE_FONTS)
    accent = rng.choice(ACCENTS)
    co = b['company']
    stem = {'proposal': f'{co} - Proposal {code} {spec["name"]}', 'quote': f'{co} quote - justice center {spec["name"].split()[0].lower()}',
            'letter': f'{co} - TCJC {spec["name"]} bid', 'short': f'{" ".join(co.split()[:2])} quote TCJC {code}',
            'bidform': f'{co} - {code} Bid Form', 'estimate': f'{co.upper()} - TCJC ESTIMATE'}[layout]
    if b['arch'] == 'revision' and not superseded:
        stem += ' REV1'
    if superseded:
        stem = f'{co} budget quote 111125'
    stem = re.sub(r'\s+', ' ', re.sub(r'[\\/:*?"<>|]', ' ', stem.replace('&', 'and'))).strip()
    bid = {
        'id': slugify(co) + ('-r0' if superseded else ''), 'pkg': code, 'pkg_name': spec['name'], 'company': co, 'file': f'{stem}.{fmt}', 'fmt': fmt, 'layout': layout,
        'accent': ('#' + accent) if fmt == 'pdf' else accent, 'font': font, 'date': when, 'ref': f"{''.join(w[0] for w in co.split())}-{rng.randint(1000, 9999)}",
        'contact': {'name': 'Estimating Department', 'phone': f"({spec['area']}) 555-01{b['n'] + (50 if superseded else 0):02d}", 'email': f'estimating@{slugify(co)}.example'},
        'intro': intro, 'lines': lines, 'total': total, 'alts': [] if superseded else b.get('alts', []), 'tax': tax, 'tax_add': None,
        'incl': ([] if q['addenda_missing'] else ['Mobilizations as required per CM/GC schedule', 'Labor and material escalation to meet schedule'])[: rng.randint(0, 2)],
        'excl': excl + (['Sales tax'] if tax == 'excluded' else []) + (['Payment and performance bond'] if rng.random() < 0.4 else []),
        'clar': clar, 'warranty': [] if superseded else (spec['warranty_ok'] if q['warranty_meets'] else spec['warranty_short']),
        'validity': q['validity'], 'addenda': [] if (q['addenda_missing'] or superseded) else ['Addendum 01'],
        'rates': engine_rates(rng) if rng.random() < 0.5 else None, 'markups': None,
    }
    if bid['rates']:
        bid['markups'] = [('Labor', '15%'), ('Material', rng.choice(['10%', '15%'])), ('Equipment', '10%'), ('Lower-tier subcontractors', '5%')]
    if tax == 'included':
        bid['clar'].append('All prices include applicable sales tax.')
    out_dir.mkdir(parents=True, exist_ok=True)
    RENDER[fmt](bid, out_dir / bid['file'])
    return bid


def engine_rates(rng):
    base = rng.uniform(62, 98)
    return [('General Foreman', r2(base * 1.12)), ('Foreman', r2(base * 1.05)), ('Journeyman', r2(base)), ('Apprentice', r2(base * 0.66))]


# ---------------------------------------------------------------- qualification facts (synthetic) designed against the policy
def design_qualification(code, bidders, leveled, rng):
    """Five bidders fail a disqualifying rule, chosen across the price range so the lowest leveled bid is one of them."""
    order = sorted(bidders, key=lambda b: leveled[b['company']]['leveledTotal'])
    for b in bidders:
        b['qual'] = {'prequal': 'Approved', 'limit': float(round(max(2.5e6, leveled[b['company']]['leveledTotal'] * rng.uniform(3, 8)), -5)),
                     'safety': round(rng.uniform(0.2, 4.6), 2), 'asked': False, 'responded': None, 'addenda_missing': False,
                     'warranty_meets': rng.random() > 0.25, 'validity': rng.choice([60, 60, 60, 90, 30]), 'fails': [], 'flags': []}
    fails = {0: 'no_response', 2: 'not_prequalified', 5: 'safety', 8: 'addenda', 12: 'limit'}
    for pos, why in fails.items():
        q = order[pos]['qual']
        q['fails'].append(why)
        if why == 'not_prequalified':
            q['prequal'] = 'Not prequalified - application incomplete'
        if why == 'safety':
            q['safety'] = round(rng.uniform(16.5, 31), 2)
            q['prequal'] = 'Approved with conditions (safety)'
        if why == 'addenda':
            q['addenda_missing'] = True
        if why == 'limit':
            q['limit'] = float(round(leveled[order[pos]['company']]['leveledTotal'] * 0.6, -4))
    for b in rng.sample([b for i, b in enumerate(order) if i not in fails], 2):      # within the mitigation band: flag, not a failure
        b['qual'].update(safety=round(rng.uniform(5.5, 12.5), 2), prequal='Approved with conditions (safety)')
        b['qual']['flags'].append('Safety score between 5 and 15: mitigation plan submitted')
    asked = order[:7] + [b for b in bidders if leveled[b['company']]['counts']['plugged'] >= 2]
    for b in asked:
        b['qual']['asked'] = True
        b['qual']['responded'] = 'no_response' not in b['qual']['fails']
    for b in bidders:
        q = b['qual']
        if not q['warranty_meets']:
            q['flags'].append('Warranty below the minimum: must be corrected before award')
        if q['validity'] < 60:
            q['flags'].append(f"Bid valid {q['validity']} days (policy asks 60)")
        q['expected_qualified'] = not q['fails']
    return order


REASON = {'no_response': 'Did not answer clarification questions by the deadline (unresponsive)', 'not_prequalified': 'Not prequalified',
          'safety': 'Predicted safety incidents above 15 with no regional safety approval', 'addenda': 'Priced without Addendum 01 (not priced against current documents)',
          'limit': 'Leveled total exceeds its single-project prequalification limit'}


# ---------------------------------------------------------------- GC-side documents
def head(ws, widths):
    for i, w in enumerate(widths):
        ws.column_dimensions[ws.cell(row=1, column=i + 1).column_letter].width = w
        ws.cell(row=1, column=i + 1).font = Font(bold=True, color='FFFFFF')
        ws.cell(row=1, column=i + 1).fill = PatternFill('solid', fgColor='1F2937')
    ws.freeze_panes = 'A2'


def write_scope_sheet(path, code, items):
    wb = XWorkbook()
    ws = wb.active
    ws.title = 'Scope Items'
    ws.append(['Key', 'Section', 'Scope item', 'Type', 'CM/GC quantity (90% CD)', 'Unit', 'Specified depth (in.)', 'Bidder Qty', 'Bidder Unit', 'Bidder Unit Price', 'Bidder Value'])
    for it in items:
        ws.append([it['key'], it['section'], it['name'], 'Price', it['qty'], it['unit'], it['depth']])
    head(ws, [9, 24, 60, 8, 18, 8, 16, 11, 11, 15, 14])
    ws.append([])
    ws.append(['', '', 'Price every item. State Included or Excluded where an item is not priced separately. Add any other priced lines under Comments.'])
    ws = wb.create_sheet('Required Warranties')
    ws.append(['System', 'Minimum warranty'])
    for s, w in SETS[code]['warranty_min']:
        ws.append([s, w])
    head(ws, [50, 90])
    ws = wb.create_sheet('CMGC Estimate (confidential)')
    ws.append(['Key', 'Scope item', 'Qty', 'Unit', 'Unit rate', 'Estimate'])
    for it in items:
        ws.append([it['key'], it['name'], it['qty'], it['unit'], it['rate'], it['estimate']])
    ws.append(['', 'TOTAL', None, None, None, r2(sum(i['estimate'] for i in items))])
    head(ws, [9, 60, 10, 8, 12, 14])
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(path))


def write_prequal(path, all_bidders, declines):
    wb = XWorkbook()
    ws = wb.active
    ws.title = 'Prequalification'
    ws.append(['Subcontractor', 'Bid package', 'Prequalification status', 'Single-project limit ($)', 'Predicted Safety Incidents', 'SDI enrolled', 'Notes'])
    for code, bs in all_bidders.items():
        for b in bs:
            q = b['qual']
            note = 'Safety mitigation plan on file' if 5 < q['safety'] <= 15 else 'No regional safety approval on file' if q['safety'] > 15 else ''
            ws.append([b['company'], f"{code} {SETS[code]['name']}", q['prequal'], q['limit'], q['safety'], 'Yes', note])
            ws.cell(row=ws.max_row, column=4).number_format = '$#,##0'
        for d in declines[code]:
            ws.append([d['company'], f"{code} {SETS[code]['name']}", 'Approved', 1000000, 2.1, 'Yes', 'Declined to bid'])
    head(ws, [36, 34, 36, 20, 18, 12, 36])
    ws.append([])
    ws.append(['SYNTHETIC roster for POC testing.'])
    wb.save(str(path))


def write_clarifications(path, all_bidders, leveled_by_code):
    wb = XWorkbook()
    ws = wb.active
    ws.title = 'Clarification Log'
    ws.append(['Bid package', 'Bidder', 'Question sent', 'Question', 'Response due', 'Response received', 'Response summary'])
    for code, bs in all_bidders.items():
        for b in bs:
            q = b['qual']
            if not q['asked']:
                continue
            lv = leveled_by_code[code][b['company']]
            ask = f"Confirm scope and quantities; {lv['counts']['plugged']} item(s) not priced" if lv['counts']['plugged'] else 'Confirm scope, quantities and inclusions for the leveled comparison'
            if q['addenda_missing']:
                ask += '; confirm Addendum 01 is included'
            if q['responded']:
                ans = 'Responded. Scope and quantities confirmed.'
                if q['addenda_missing']:
                    ans = 'Responded. Bidder confirms the price does not include Addendum 01 and will not re-price.'
                if 5 < q['safety'] <= 15:
                    ans += ' Safety mitigation plan submitted.'
                if q['safety'] > 15:
                    ans += ' No regional safety approval has been obtained.'
                ws.append([f"{code} {SETS[code]['name']}", b['company'], date(2025, 11, 19), ask, date(2025, 11, 21), date(2025, 11, 20), ans])
            else:
                ws.append([f"{code} {SETS[code]['name']}", b['company'], date(2025, 11, 19), ask, date(2025, 11, 21), 'NO RESPONSE', 'No response by the 2025-11-21 deadline.'])
    head(ws, [32, 36, 14, 70, 14, 18, 70])
    ws.append([])
    ws.append(['SYNTHETIC log for POC testing.'])
    wb.save(str(path))


def write_brief(path, items_by_code):
    L = ['# Teton County Justice Center: bid packages with 20 bidders', '',
         '> SYNTHETIC test documents. Scope items and the starting prices come from the TCJC leveling workbook; bidders and documents are invented.', '',
         '- Project: Teton County Justice Center, Jackson, Wyoming', '- Documents: FGMP / 90% Construction Documents', '- Building gross area: 80,120 SF',
         '- Delivery: CM/GC. Bids are submitted to the CM/GC, who levels them and recommends an award.', '- The project is tax exempt.',
         '- Invitation to bid issued: 2025-10-27', '- Addendum 01 issued: 2025-11-10 (site packages: revised storm and paving details)',
         '- Bids due: 2025-11-18, 2:00 PM Mountain Time', '- Clarification responses due within two business days of the question.', '', '## Bid packages', '']
    for code, items in items_by_code.items():
        L.append(f"- {code} {SETS[code]['name']}: {len(items)} scope items, CM/GC estimate ${sum(i['estimate'] for i in items):,.0f}")
    path.write_text('\n'.join(L) + '\n')


def write_plug_policy(path):
    y = {'version': 1,
         'defaults': {'plug_when': ['excluded', 'not_priced'], 'method': 'average_of_bidders', 'fallback': ['gc_estimate'],
                      'comparable_pool': {'exclude_self': True, 'exclude_unresponsive': True, 'min_pool': 2, 'outlier_trim_pct': 50, 'outlier_trim_min_pool': 3}},
         'quantity_normalization': {'convert_to': 'gc_unit', 'threshold_pct': 5.0, 'over_threshold': 'reextend_unit_rate_at_gc_quantity', 'within_threshold': 'carry_as_bid'},
         'packages': {code: {'allowances_all_bidders': [], 'items': {}} for code in SETS}}
    path.write_text('# Plugging policy for the 20-bidder packages. SYNTHETIC.\n' + yaml.safe_dump(y, sort_keys=False))


# ---------------------------------------------------------------- answer key
def leveled_view(res):
    return {b['name']: b for b in res['bidders']}


def write_answer_key(path_json, code, items, bidders, res, docs, declines, superseded, order):
    lv = leveled_view(res)
    qualified = [b for b in order if b['qual']['expected_qualified']]
    low_q = qualified[0]
    lowq_total = lv[low_q['company']]['leveledTotal']
    acceptable = [b['company'] for b in qualified if lv[b['company']]['leveledTotal'] <= lowq_total * 1.03]
    out_bidders = []
    for b in bidders:
        e = lv[b['company']]
        lines = []
        for it in items:
            c, t = e['cells'][it['key']], b['truth'][it['key']]
            lines.append({'item': it['key'], 'scope_item': it['name'], 'status': t['status'], 'state': c['state'],
                          'as_bid': {k: t.get(k) for k in ('quantity', 'unit', 'unit_price', 'amount', 'depth_in')},
                          'conversion': ({'factor': c['unitNorm']['factor'], 'explanation': c['unitNorm']['explanation'], 'source': 'stated in the bid (model must read it)' if t.get('model_only_conversion') else 'standard table'}
                                         if c.get('unitNorm') and c['unitNorm']['applied'] else None),
                          'quantity_check': c.get('qtyNorm'), 'leveled_value': c['value'], 'adjustment': c['adjustment'],
                          'plug': {'method': c['plug']['method'], 'value': c['plug']['value'], 'formula': c['plug']['formula']} if c.get('plug') else None,
                          'checks': c.get('flags') or []})
        q = b['qual']
        out_bidders.append({
            'company': b['company'], 'document': docs[b['company']], 'pricing_pattern': b['arch'],
            'as_bid_total': e['asBid'], 'stated_total': docs[b['company']]['total'], 'extras': b.get('extras', []), 'alternates': b.get('alts', []),
            'arithmetic_slip': b.get('slipped'), 'quantity_adjustments': e['quantityAdjustments'], 'plug_total': e['plugs'], 'base_bid': e['baseBid'],
            'leveled_total': e['leveledTotal'], 'scope_priced': e['scopePriced'], 'counts': e['counts'],
            'qualification': {'prequalification': q['prequal'], 'single_project_limit': q['limit'], 'predicted_safety_incidents': q['safety'],
                              'clarification_asked': q['asked'], 'clarification_answered': q['responded'], 'addendum_01_acknowledged': not q['addenda_missing'],
                              'warranty_meets_minimum': q['warranty_meets'], 'validity_days': q['validity'], 'tax': b.get('tax', 'excluded'),
                              'expected_qualified': q['expected_qualified'], 'disqualified_because': [REASON[f] for f in q['fails']], 'flags': q['flags']},
            'lines': lines})
    key = {
        'package': code, 'name': SETS[code]['name'], 'note': ('SYNTHETIC. Scope items and starting prices are from the TCJC workbook tab; bidders, documents and '
                                                               'qualification facts are invented. Leveled figures are the leveling engine run on the true contents of each document.'),
        'settings': SETTINGS, 'items': [{k: v for k, v in it.items() if k not in ('market', 'real_values')} for it in items],
        'bidders': out_bidders, 'declined': declines, 'superseded': superseded,
        'expected': {'qualified_count': len(qualified), 'lowest_leveled_overall': order[0]['company'],
                     'lowest_leveled_qualified': low_q['company'], 'acceptable_recommendations': acceptable,
                     'rule': 'The policy awards to the lowest responsive, responsible bidder on leveled total; a bidder within 3% may be chosen on best-value grounds.'},
        'ranking_by_leveled_total': [{'company': b['company'], 'leveled_total': lv[b['company']]['leveledTotal'], 'expected_qualified': b['qual']['expected_qualified']} for b in order],
    }
    path_json.write_text(json.dumps(key, indent=1, default=str) + '\n')
    return key


def write_answer_xlsx(path, keys):
    wb = XWorkbook()
    ws = wb.active
    ws.title = 'Summary'
    ws.append(['Package', 'Rank', 'Bidder', 'Pattern', 'Document', 'As bid', 'Qty adjustments', 'Plugs', 'Leveled total', 'Scope priced', 'Expected qualified', 'Why not'])
    for key in keys.values():
        by = {b['company']: b for b in key['bidders']}
        for i, r in enumerate(key['ranking_by_leveled_total'], 1):
            b = by[r['company']]
            ws.append([f"{key['package']} {key['name']}", i, b['company'], b['pricing_pattern'], b['document']['file'], b['as_bid_total'], b['quantity_adjustments'],
                       b['plug_total'], b['leveled_total'], b['scope_priced'], 'Yes' if b['qualification']['expected_qualified'] else 'No',
                       '; '.join(b['qualification']['disqualified_because'])])
            for c in ws[ws.max_row][5:9]:
                c.number_format = '$#,##0.00'
            ws.cell(row=ws.max_row, column=10).number_format = '0%'
            if b['company'] == key['expected']['lowest_leveled_qualified']:
                for c in ws[ws.max_row]:
                    c.fill = PatternFill('solid', fgColor='E9E5FB')
    head(ws, [32, 6, 34, 11, 52, 15, 15, 14, 15, 11, 10, 60])
    for key in keys.values():
        ws = wb.create_sheet(key['package'] + ' tally')
        bs = key['bidders']
        ws.append(['Key', 'Scope item', 'GC qty', 'Unit', 'GC estimate'] + [b['company'] for b in bs])
        for it in key['items']:
            ws.append([it['key'], it['name'], it['qty'], it['unit'], it['estimate']] + [next(l for l in b['lines'] if l['item'] == it['key'])['leveled_value'] for b in bs])
            for j, b in enumerate(bs):
                ln = next(l for l in b['lines'] if l['item'] == it['key'])
                c = ws.cell(row=ws.max_row, column=6 + j)
                c.number_format = '$#,##0'
                if ln['plug']:
                    c.fill = PatternFill('solid', fgColor='FCE8B8')
                elif ln['state'] == 'included':
                    c.value = 'Included'
                elif ln['conversion'] or (ln['quantity_check'] or {}).get('applied'):
                    c.fill = PatternFill('solid', fgColor='DCE9FB')
        for label, f in [('As bid', 'as_bid_total'), ('Leveled total', 'leveled_total')]:
            ws.append(['', label, None, None, None] + [b[f] for b in bs])
        head(ws, [7, 48, 9, 6, 13] + [22] * len(bs))
    wb.save(str(path))


def write_readme(keys):
    L = ['# TCJC: 20 subcontractors per package (complete scope)', '',
         'Third sample set for the bid-leveling POC. Each package uses its **complete scope** from the TCJC leveling workbook: every line on the tab that the GC '
         'estimated or that two or more real bidders priced. Twenty fictional subcontractors bid each package, plus one decline notice and one superseded quote.', '',
         '> SYNTHETIC. Scope items and starting prices come from the workbook; bidders, pricing patterns, documents and qualification facts are invented. '
         'Every bid document is stamped SYNTHETIC TEST DATA.', '',
         '## Packages', '', '| Package | Scope items | Proposals | GC estimate | Expected qualified | Lowest leveled (any) | Lowest leveled qualified |', '|---|---|---|---|---|---|---|']
    for key in keys.values():
        est = sum(i['estimate'] for i in key['items'])
        L.append(f"| {key['package']} {key['name']} | {len(key['items'])} | {len(key['bidders'])} + 1 superseded + 1 decline | ${est:,.0f} | "
                 f"{key['expected']['qualified_count']} of {len(key['bidders'])} | {key['expected']['lowest_leveled_overall']} | {key['expected']['lowest_leveled_qualified']} |")
    L += ['', '## What the documents exercise', '',
          '- **Formats and layouts:** PDF proposals and quotes, Word letters and plain-text quotes, Excel bid forms and the bidder\'s own estimate sheets.',
          '- **Pricing patterns:** complete bids, low bids with scope gaps, high bids, bids that leave out a whole section, items folded into other lines ("included in ..."), '
          'a lump-sum-only bid, erratic item pricing, and a revised bid that supersedes an earlier quote.',
          '- **Unit normalization:** square yards, metres, cubic metres, cubic yards at a stated depth, square feet at a different depth, and two units that only the bid '
          'text explains (tons of cobble with a stated coverage; storm pipe priced per 20 ft joint).',
          '- **Quantity normalization:** about a fifth of quantity lines differ from the GC takeoff by 6 to 18%; the rest are within 3%.',
          '- **Other lines:** bidder-added items (mobilization, bonds, freight), tax credits shown as negative lines, alternates priced outside the total, and one '
          'arithmetic slip per package (a line amount that is not quantity x unit price; the bid is carried as written).',
          '- **Qualification:** in each package five bidders fail a disqualifying rule of the award policy, spread across the price range; the lowest leveled bid is one '
          'of them. The facts are in `gc/subcontractor_prequal.xlsx`, `gc/bid_clarification_log.xlsx` and the bids themselves (Addendum 01 not acknowledged).', '',
          '## Files', '', '```', 'gc/', '  awarding_policy.md / .docx      award rules (lowest responsive, responsible bidder; prequalification; safety; addenda)',
          '  plugging_policy.yaml            default plug method: average of the other bids, then the GC estimate', '  subcontractor_prequal.xlsx      status, limit, safety score',
          '  bid_clarification_log.xlsx      questions and who answered', '  project_brief.md', '  <package>/scope_sheet.xlsx      complete scope with GC quantities; GC estimate tab',
          'bids/<package>/                   20 proposals + 1 superseded quote + 1 decline', 'answer_key/', '  <package>.json                  true reading of every line, leveled values, plugs, totals, qualification, expected award',
          '  answer_key.xlsx                 summary and a tally per package', '```', '', '## Regenerating', '', '```',
          'uv run --no-project --with reportlab --with python-docx --with openpyxl --with pypdf --with pyyaml tools/gen_samples/twenty.py', '```', '']
    (OUT / 'README.md').write_text('\n'.join(L))


# ---------------------------------------------------------------- main
def main():
    wb = Workbook(SRC)
    base = {c: load_package(wb, c, s) for c, s in BASE_PACKAGES.items()}
    f, trate = gc_docs.facts(wb), gc_docs.textura_rate(base)
    for sub in ('gc', 'bids', 'answer_key'):
        shutil.rmtree(OUT / sub, ignore_errors=True)
    (OUT / 'gc').mkdir(parents=True)
    (OUT / 'answer_key').mkdir(parents=True)
    used, items_by, bidders_by, leveled_by, keys, files, declines_by, problems = set(), {}, {}, {}, {}, [], {}, []
    for code, spec in SETS.items():
        rng = random.Random(spec['seed'])
        pkg = load_package(wb, code, {'sheet': spec['sheet'], 'est_block': spec['est_block'], 'name': spec['name'], 'slug': spec['slug']})
        items, extras_tpl = complete_scope(code, pkg, rng)
        bidders = make_bidders(code, items, extras_tpl, rng, used)
        for b in bidders:                               # true contents of each document, then the engine on those contents
            b['qual'] = {'addenda_missing': False}
            b['lines'], b['truth'] = build_lines(b, items, random.Random(spec['seed'] * 100 + b['n']))
            b['excluded_names'] = [it['name'] for it in items if b['status'][it['key']] == 'excluded']
        raw = [{'id': f"b{b['n']:02d}", 'name': b['company'], 'cells': b['truth'], 'extras': b.get('extras', [])} for b in bidders]
        res = engine.level(items, raw, SETTINGS)
        lv = leveled_view(res)
        order = design_qualification(code, bidders, lv, rng)
        out_dir = OUT / 'bids' / spec['slug']
        docs, superseded = {}, []
        for b in bidders:
            bid = render_bid(code, b, b['lines'], random.Random(spec['seed'] * 1000 + b['n']), out_dir)
            if abs(bid['total'] - lv[b['company']]['asBid']) > 0.02:
                problems.append(f"{code} {b['company']}: document total {bid['total']} != engine as-bid {lv[b['company']]['asBid']}")
            docs[b['company']] = {'file': bid['file'], 'format': bid['fmt'], 'layout': bid['layout'], 'date': str(bid['date']), 'total': bid['total']}
            files.append((bid, out_dir / bid['file']))
            if b['arch'] == 'revision':
                old_lines, _ = build_lines(dict(b, slip=False, slipped=None), items, random.Random(spec['seed'] * 100 + b['n']), price_factor=1.045)
                old = render_bid(code, b, old_lines, random.Random(spec['seed'] * 7 + b['n']), out_dir, superseded=True)
                files.append((old, out_dir / old['file']))
                superseded.append({'company': b['company'], 'file': old['file'], 'date': str(old['date']), 'total': old['total'], 'superseded_by': bid['file']})
        dname = f"{rng.choice([p for p in PLACES if not any(p in u for u in used)])} {rng.choice(spec['suffixes'])}"
        used.add(dname)
        drng = random.Random(spec['seed'] + 1)
        fmt = drng.choice(['docx', 'pdf'])
        decline = {'id': slugify(dname), 'pkg': code, 'pkg_name': spec['name'], 'company': dname, 'fmt': fmt, 'layout': 'decline' if fmt == 'docx' else 'email',
                   'file': f"{dname} - no bid.docx" if fmt == 'docx' else f"RE_ TCJC {code} {spec['name'].split()[0]} - bid invite.pdf",
                   'accent': '333333' if fmt == 'docx' else '#000000', 'font': 'Calibri' if fmt == 'docx' else 'Helvetica', 'date': date(2025, 11, 14),
                   'contact': {'name': 'Estimating Department', 'phone': f"({spec['area']}) 555-0199", 'email': f'estimating@{slugify(dname)}.example'},
                   'body': ['Thank you for the invitation to bid this package for the Teton County Justice Center.',
                            'We will not be submitting a bid. Our crews are committed through next season and we cannot meet the schedule.',
                            'Please keep us on your list for future work.']}
        RENDER[fmt](decline, out_dir / decline['file'])
        files.append((decline, out_dir / decline['file']))
        declines_by[code] = [{'company': dname, 'file': decline['file']}]
        write_scope_sheet(OUT / 'gc' / spec['slug'] / 'scope_sheet.xlsx', code, items)
        keys[code] = write_answer_key(OUT / 'answer_key' / f"{spec['slug']}.json", code, items, bidders, res, docs, declines_by[code], superseded, order)
        items_by[code], bidders_by[code], leveled_by[code] = items, bidders, lv
        e = keys[code]['expected']
        print(f"{code} {spec['name']}: {len(items)} scope items, {len(bidders)} bidders, {len(extras_tpl)} bidder-only lines in the workbook | "
              f"expected qualified {e['qualified_count']} | lowest {e['lowest_leveled_overall']} | lowest qualified {e['lowest_leveled_qualified']}")
    pk = {c: {'code': c, 'name': s['name'], 'warranty_min': s['warranty_min']} for c, s in SETS.items()}
    gc_docs.write_policy(OUT / 'gc', f, trate, pk, sec5=[
        'Scope gaps and quantity differences are leveled according to the Plugging Policy (plugging_policy.yaml): a gap is plugged at the average of the other '
        'bidders\' prices for the item, or the CM/GC estimate when fewer than two comparable prices exist; a quantity more than 5% from the CM/GC takeoff is '
        're-extended at the bidder\'s unit rate.',
        'Bids are compared on Leveled Total = bid as submitted + quantity adjustments + plugs. Sales tax is excluded (the project is tax exempt).'])
    write_plug_policy(OUT / 'gc' / 'plugging_policy.yaml')
    write_prequal(OUT / 'gc' / 'subcontractor_prequal.xlsx', bidders_by, {c: [{'company': d['company']} for d in v] for c, v in declines_by.items()})
    write_clarifications(OUT / 'gc' / 'bid_clarification_log.xlsx', bidders_by, leveled_by)
    write_brief(OUT / 'gc' / 'project_brief.md', items_by)
    write_answer_xlsx(OUT / 'answer_key' / 'answer_key.xlsx', keys)
    write_readme(keys)
    problems += verify.check_files(files)
    print(f'\n{len(files)} documents written to {OUT}')
    if problems:
        print('PROBLEMS:\n  ' + '\n  '.join(problems[:40]))
        sys.exit(1)
    print('Verification passed: every amount found again in its file; document totals equal the engine as-bid totals.')


if __name__ == '__main__':
    main()
