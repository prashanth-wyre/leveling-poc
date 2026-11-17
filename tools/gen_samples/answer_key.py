"""Answer key: expected leveled result per package, as JSON and as a readable workbook."""
import json

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from specs import CLARIFICATIONS, PREQUAL
from tcjc import shift

PLUG = PatternFill('solid', fgColor='FFF2A8')
HDR = PatternFill('solid', fgColor='1F2937')
REC = PatternFill('solid', fgColor='C8E6C9')

SYNTHETIC_FIELDS = ['warranty', 'prequalification.status', 'prequalification.single_project_limit',
                    'prequalification.sdi_enrolled', 'clarification', 'bid validity, addenda, labor rates and mark-ups in the bid documents',
                    'bid dates and references', 'the split of Rodac into an original quote and a revised bid']


def bidder_entry(pkg, block, name, bids, declines):
    t = pkg['tab']
    mine = [b for b in bids if b['pkg'] == pkg['code'] and b['company'] == name]
    dec = [d for d in declines if d['pkg'] == pkg['code'] and d['company'] == name]
    status, limit, sdi = PREQUAL[name]
    e = dict(company=name, workbook_block=block,
             prequalification=dict(status=status, single_project_limit=limit, sdi_enrolled=sdi,
                                   predicted_safety_incidents=t.num(shift(block, 4), 8)))
    if dec:
        e.update(status='declined', documents=[dec[0]['file']])
        return e
    cur = next(b for b in mine if not b['superseded'])
    lev = cur['lev']
    clar = [c for c in CLARIFICATIONS if c[0] == pkg['code'] and c[1] == name]
    e.update(
        status='priced',
        documents=[dict(file=b['file'], format=b['fmt'], date=str(b['date']),
                        role='superseded - do not level' if b['superseded'] else 'current bid',
                        total_as_written=b['total']) for b in mine],
        responsive=cur.get('responsive', True),
        clarification=(dict(sent=str(clar[0][2]), responded=clar[0][4] is not None, summary=clar[0][5]) if clar else None),
        lines=[dict(workbook_row=l['row'], scope_item=l['scope_item'], bidder_description=l['desc'], qty=l['qty'], unit=l['unit'],
                    unit_price=l['up'], amount=l['amt']) for l in cur['lines']],
        tax_treatment=cur['tax'], sales_tax_quoted_outside_total=cur['tax_add'],
        alternates=[dict(description=t.text('C', a['row']), amount=a['amt']) for a in cur['alts']],
        exclusions=cur['excl'],
        warranty=dict(offered=cur['warranty'], meets_minimum=cur['warranty_meets']),
        bid_validity_days=cur['validity'], addenda_acknowledged=cur['addenda'],
        expected_flags=cur['flags'], **lev)
    return e


def build(pkg, bids, declines):
    t, k = pkg['tab'], pkg['k']
    entries = [bidder_entry(pkg, b, n, bids, declines) for b, n in pkg['bidders']]
    rec = next(n for b, n in pkg['bidders'] if t.text(b, k['rec']) == n)
    priced = [e for e in entries if e['status'] == 'priced']
    ok = sorted((e for e in priced if e['responsive']), key=lambda e: e['total_package_value'])
    if ok[0]['company'] != rec:
        raise AssertionError(f"{pkg['code']}: lowest responsive is {ok[0]['company']}, workbook recommends {rec}")
    rank = sorted(priced, key=lambda e: e['total_package_value'])
    pos = [e['company'] for e in rank].index(rec) + 1
    skipped = [e['company'] for e in rank[:pos - 1]]
    why = f'Lowest responsive, responsible bidder on Total Package Value (${ok[0]["total_package_value"]:,.2f}).'
    if skipped:
        why += f' {pos - 1} lower-priced bidder(s) are UNRESPONSIVE and excluded: ' + ', '.join(skipped) + '.'
    eb = pkg['est_block']
    a, b = pkg['est_rows']
    return dict(
        package=pkg['code'], name=pkg['name'], source_workbook_tab=pkg['sheet'],
        cmgc_estimate=dict(total=pkg['estimate'], lines=[
            dict(description=t.text('C', r), qty=t.num(shift(eb, 1), r), unit=t.text(shift(eb, 2), r), value=t.money(shift(eb, 4), r))
            for r in range(a, b + 1) if t.text('C', r)]),
        formulas=dict(base_bid_value='sub_bid_as_submitted + gc_plug_total', subcontract_value='base_bid_value + textura',
                      total_package_value='subcontract_value + sales_tax + sdi', variance='total_package_value - cmgc_estimate.total'),
        bidders=entries, recommended_bidder=rec, award_amount=ok[0]['total_package_value'], rationale=why,
        ranking_by_total_package_value=[dict(company=e['company'], total_package_value=e['total_package_value'], responsive=e['responsive'])
                                        for e in rank],
        provenance=dict(
            from_workbook='line amounts, quantities, unit prices, base bid value, Textura, SDI, sales tax, subcontract value, '
                          'total package value, alternates, recommended bidder, UNRESPONSIVE marks, predicted safety incidents',
            inferred='which lines are the bid and which are CM/GC plugs, for bidders other than the recommended one '
                     '(the workbook only codes cost categories for the recommended bidder)',
            synthetic=SYNTHETIC_FIELDS))


def write(out, pkgs, bids, declines):
    out.mkdir(parents=True, exist_ok=True)
    keys = {c: build(p, bids, declines) for c, p in pkgs.items()}
    for c, key in keys.items():
        (out / f"{pkgs[c]['slug']}.json").write_text(json.dumps(key, indent=2) + '\n')

    wb = Workbook()
    ws = wb.active
    ws.title = 'Summary'
    ws.append(['Package', 'Bidder', 'Status', 'Bid as submitted', 'CM/GC plugs', 'Base bid value', 'Total package value',
               'Variance vs estimate', 'Var %', 'Responsive', 'Warranty meets minimum', 'Recommended'])
    for key in keys.values():
        for e in key['bidders']:
            if e['status'] == 'declined':
                ws.append([f"{key['package']} {key['name']}", e['company'], 'Declined to bid'])
                continue
            ws.append([f"{key['package']} {key['name']}", e['company'], 'Priced', e['sub_bid_as_submitted'], e['gc_plug_total'],
                       e['base_bid_value'], e['total_package_value'], e['variance'], e['variance_pct'] / 100,
                       'Yes' if e['responsive'] else 'UNRESPONSIVE', {True: 'Yes', False: 'No'}[e['warranty']['meets_minimum']],
                       'RECOMMENDED' if e['company'] == key['recommended_bidder'] else ''])
            row = ws[ws.max_row]
            for i in (3, 4, 5, 6, 7):
                row[i].number_format = '$#,##0.00'
            row[8].number_format = '0.0%'
            if row[11].value:
                for c in row:
                    c.fill = REC
    for i, w in enumerate([32, 34, 16, 18, 16, 18, 20, 20, 9, 16, 22, 16]):
        ws.column_dimensions[chr(65 + i)].width = w
        ws.cell(row=1, column=i + 1).font = Font(bold=True, color='FFFFFF')
        ws.cell(row=1, column=i + 1).fill = HDR
    ws.append([])
    ws.append(['Totals tie to the TCJC workbook tabs. Warranty and Responsive-by-clarification columns rest on synthetic inputs; see the JSON files.'])

    for c, p in pkgs.items():
        t, k, key = p['tab'], p['k'], keys[c]
        priced = [(b, n) for b, n in p['bidders'] if any(e['company'] == n and e['status'] == 'priced' for e in key['bidders'])]
        ws = wb.create_sheet(p['slug'][:31])
        ws.append(['Row', 'Scope item (workbook wording)', 'CM/GC qty', 'Unit'] + [n for _, n in priced])
        plug_cells = {(e['company'], g['row']) for e in key['bidders'] if e['status'] == 'priced' for g in e['gc_plugs']}
        eb = p['est_block']
        for r in range(p['scope_start'], k['base']):
            vals = [t.v(shift(b, 4), r) for b, _ in priced]
            if not t.text('C', r) or all(v is None for v in vals):
                continue
            ws.append([r, t.text('C', r), t.num(shift(eb, 1), r), t.text(shift(eb, 2), r)] +
                      [round(v, 2) if isinstance(v, float) else v for v in vals])
            for i, (_, n) in enumerate(priced):
                cell = ws.cell(row=ws.max_row, column=5 + i)
                cell.number_format = '$#,##0.00'
                if (n, r) in plug_cells:
                    cell.fill = PLUG
        ws.append([])
        by = {e['company']: e for e in key['bidders']}
        for label, f in [('Bid as submitted (current bid document)', 'sub_bid_as_submitted'), ('CM/GC plugs (shaded cells)', 'gc_plug_total'),
                         ('BASE BID VALUE', 'base_bid_value'), ('Textura', 'textura'), ('SUBCONTRACT VALUE', 'subcontract_value'),
                         ('Sales tax', 'sales_tax'), ('SDI', 'sdi'), ('TOTAL PACKAGE VALUE', 'total_package_value'),
                         ('Variance from CM/GC estimate', 'variance')]:
            ws.append([None, label, None, None] + [by[n][f] for _, n in priced])
            for cell in ws[ws.max_row]:
                cell.number_format = '$#,##0.00'
                cell.font = Font(bold=label.isupper())
        ws.append([None, 'Responsive', None, None] + ['Yes' if by[n]['responsive'] else 'UNRESPONSIVE' for _, n in priced])
        ws.append([None, 'Recommended bidder', None, None] + ['RECOMMENDED' if n == key['recommended_bidder'] else '' for _, n in priced])
        ws.append([])
        ws.append([None, f"CM/GC estimate: ${p['estimate']:,.2f}.  {key['rationale']}"])
        ws.column_dimensions['A'].width, ws.column_dimensions['B'].width = 6, 62
        for i in range(2 + len(priced)):
            ws.column_dimensions[chr(67 + i)].width = 12 if i < 2 else 24
        for cell in ws[1]:
            cell.font, cell.fill = Font(bold=True, color='FFFFFF'), HDR
            cell.alignment = Alignment(wrap_text=True, vertical='top')
        ws.freeze_panes = 'C2'
    wb.save(str(out / 'answer_key.xlsx'))
    return keys
