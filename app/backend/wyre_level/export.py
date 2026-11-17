"""Excel export of a leveled package: the table, plugs and adjustments, scores, explanations."""
import io

from openpyxl import Workbook
from openpyxl.comments import Comment
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

HDR = PatternFill('solid', fgColor='0B2A4A')
SEC = PatternFill('solid', fgColor='EEF1F5')
PLUG = PatternFill('solid', fgColor='FCE8B8')
ADJ = PatternFill('solid', fgColor='DCE9FB')
REC = PatternFill('solid', fgColor='E9E5FB')
MONEY = '$#,##0'


def _head(ws, row, widths):
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
        c = ws.cell(row=row, column=i)
        c.font, c.fill = Font(bold=True, color='FFFFFF'), HDR
        c.alignment = Alignment(wrap_text=True, vertical='top')


def build(result):
    wb = Workbook()
    bidders, items = result['bidders'], result['items']
    by_key = {i['key']: i for i in items}

    ws = wb.active
    ws.title = 'Leveled bids'
    ws.append([f"{result['package']['code']} {result['package']['name']}", 'Unit', 'GC qty', 'GC estimate'] + [b['name'] for b in bidders])
    _head(ws, 1, [46, 8, 12, 14] + [22] * len(bidders))
    ws.append(['Outcome', None, None, None] + [('Recommended' if b['band'] == 'recommended' else f"Rank {b['rank']}" if b['qualified'] else 'Did not qualify') for b in bidders])
    ws.append(['Weighted score', None, None, None] + [b['score'] for b in bidders])
    for sec in result['sections']:
        ws.append([sec['name']])
        for c in ws[ws.max_row]:
            c.fill, c.font = SEC, Font(bold=True)
        for k in sec['keys']:
            it = by_key[k]
            ws.append([it['name'], it.get('unit'), it.get('qty'), it.get('estimate')] + [b['cells'][k]['value'] for b in bidders])
            r = ws.max_row
            ws.cell(row=r, column=4).number_format = MONEY
            for j, b in enumerate(bidders):
                cell, c = ws.cell(row=r, column=5 + j), b['cells'][k]
                cell.number_format = MONEY
                if c['state'] == 'included':
                    cell.value = 'Included'
                if c['state'] == 'plugged':
                    cell.fill = PLUG
                elif (c.get('qtyNorm') or {}).get('applied') or (c.get('unitNorm') or {}).get('applied'):
                    cell.fill = ADJ
                note = (c.get('note') or {}).get('full')
                if note:
                    cell.comment = Comment(note[:900], 'Wyre AI')
        ws.append([f"{sec['name']} total", None, None, None] + [sum((b['cells'][k]['value'] or 0) for k in sec['keys']) for b in bidders])
        for c in ws[ws.max_row]:
            c.font, c.number_format = Font(bold=True), MONEY
    for label, f in [('Other bid lines (bidder-added)', 'extrasTotal'), ('GC allowances', 'allowanceTotal'), ('Base bid', 'baseBid'),
                     ('Plugs', 'plugs'), ('Leveled total', 'leveledTotal')]:
        ws.append([label, None, None, None] + [b[f] for b in bidders])
        for c in ws[ws.max_row]:
            c.number_format = MONEY
            c.font = Font(bold=label in ('Leveled total', 'Base bid'))
    ws.append([])
    ws.append(['Shading: amber = plugged by the GC; blue = unit or quantity normalized. Cell comments carry the analysis.'])
    ws.freeze_panes = 'E2'
    for j, b in enumerate(bidders):
        if b['band'] == 'recommended':
            ws.cell(row=1, column=5 + j).fill = PatternFill('solid', fgColor='5B45C9')

    ws = wb.create_sheet('Normalization and plugs')
    ws.append(['Bidder', 'Scope item', 'What happened', 'As bid qty', 'As bid unit', 'As bid amount', 'Converted qty (GC unit)', 'GC qty', 'Variance %',
               'Adjustment', 'Plug method', 'Plug value', 'Formula / conversion', 'Estimator override'])
    _head(ws, 1, [28, 40, 26, 12, 10, 14, 16, 12, 11, 13, 24, 13, 60, 18])
    for b in bidders:
        for k, c in b['cells'].items():
            un, qn, p = c.get('unitNorm') or {}, c.get('qtyNorm') or {}, c.get('plug')
            what = []
            if un.get('applied'):
                what.append('Unit normalized')
            if qn.get('applied'):
                what.append('Quantity normalized')
            if p:
                what.append('Plugged')
            if c.get('override'):
                what.append('Override')
            if not what:
                continue
            ws.append([b['name'], by_key[k]['name'], ', '.join(what), c['asBid'].get('qty'), c['asBid'].get('unit'), c['asBid'].get('amount'),
                       un.get('qtyInGcUnit'), qn.get('gcQty'), qn.get('variancePct'), c.get('adjustment') or None,
                       p['label'] if p else None, p['value'] if p else None, (p['formula'] if p else un.get('explanation')),
                       (c['override']['action'] if c.get('override') else None)])
            for col in (6, 10, 12):
                ws.cell(row=ws.max_row, column=col).number_format = MONEY

    ws = wb.create_sheet('Scores')
    crit = result['policy']['criteria']
    ws.append(['Bidder', 'Outcome', 'Weighted score', 'Leveled total', 'Base bid', 'Plugs', 'Scope priced'] + [f"{c['ordinal']}. {c['name']} ({c['weight']:g}%)" for c in crit] + ['Rules failed'])
    _head(ws, 1, [30, 18, 12, 14, 14, 12, 12] + [24] * len(crit) + [60])
    for b in bidders:
        by = {r['criterionId']: r for r in b['ratings']}
        ws.append([b['name'], 'Recommended' if b['band'] == 'recommended' else f"Rank {b['rank']}" if b['qualified'] else 'Did not qualify', b['score'],
                   b['leveledTotal'], b['baseBid'], b['plugs'], b['scopePriced']] +
                  [f"{by[c['id']]['points']:.0f} pts ({by[c['id']]['label']})" if c['id'] in by else '' for c in crit] + ['; '.join(b['reasons'])])
        r = ws.max_row
        for col in (4, 5, 6):
            ws.cell(row=r, column=col).number_format = MONEY
        ws.cell(row=r, column=7).number_format = '0%'
        if b['band'] == 'recommended':
            for c in ws[r]:
                c.fill = REC

    ws = wb.create_sheet('Explanations')
    ws.append(['Bidder', 'Headline', 'Summary', 'Strengths', 'Weaknesses', 'Deciding factors', 'What would change the outcome'])
    _head(ws, 1, [28, 40, 70, 50, 50, 50, 50])
    for b in bidders:
        e = b.get('explanation') or {}
        ws.append([b['name'], e.get('headline'), e.get('summary'), '\n'.join(e.get('strengths') or []), '\n'.join(e.get('weaknesses') or []),
                   '\n'.join(e.get('deciding_factors') or []), e.get('what_would_change')])
        for c in ws[ws.max_row]:
            c.alignment = Alignment(wrap_text=True, vertical='top')

    ws = wb.create_sheet('Scope item analysis')
    ws.append(['Scope item', 'Headline', 'Analysis', 'Priced by', 'Min', 'Median', 'Max', 'GC estimate', 'Flag'])
    _head(ws, 1, [40, 36, 90, 10, 12, 12, 12, 12, 8])
    for it in items:
        r = result['rows'][it['key']]
        n = r.get('note') or {}
        ws.append([it['name'], n.get('headline'), n.get('full'), r['n'], r['min'], r['med'], r['max'], it.get('estimate'), 'Yes' if n.get('flag') else ''])
        for col in (5, 6, 7, 8):
            ws.cell(row=ws.max_row, column=col).number_format = MONEY
        ws.cell(row=ws.max_row, column=3).alignment = Alignment(wrap_text=True, vertical='top')
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()
