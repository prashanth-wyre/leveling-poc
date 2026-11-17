"""Word (python-docx) and Excel (openpyxl) bids."""
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt, RGBColor
from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from model import SYNTH_NOTICE, money, qty_str, table_rows, tax_text
from specs import PROJECT

# ------------------------------------------------------------------ Word


def _docx(bid):
    d = Document()
    d.styles['Normal'].font.name = bid['font']
    d.styles['Normal'].font.size = Pt(10.5)
    d.core_properties.author = bid['company']
    fp = d.sections[0].footer.paragraphs[0]
    fp.text = SYNTH_NOTICE
    fp.runs[0].font.size = Pt(7)
    return d


def _head(d, bid, size=20):
    r = d.add_paragraph().add_run(bid['company'])
    r.bold, r.font.size, r.font.color.rgb = True, Pt(size), RGBColor.from_string(bid['accent'])
    c = bid['contact']
    d.add_paragraph(f"{c['phone']}   {c['email']}")


def _list(d, title, items):
    if not items:
        return
    d.add_paragraph().add_run(title).bold = True
    for it in items:
        d.add_paragraph(it, style='List Bullet')


def render_docx(bid, path):
    d = _docx(bid)
    c, dt = bid['contact'], bid['date']
    if bid['layout'] == 'decline':
        _head(d, bid, 16)
        d.add_paragraph(dt.strftime('%B %d, %Y'))
        d.add_paragraph(f"Re: {PROJECT['name']} - Bid Package {bid['pkg']} {bid.get('pkg_name', 'Roofing')}")
        for p in bid['body']:
            d.add_paragraph(p)
        d.add_paragraph(f"Sincerely,\n{c['name']}\n{bid['company']}")
    elif bid['layout'] == 'letter':
        _head(d, bid)
        d.add_paragraph(f"{dt.strftime('%B %d, %Y')}\nReference: {bid['ref']}")
        d.add_paragraph(f"CM/GC Preconstruction\nRE: {PROJECT['name']}, {PROJECT['location']} - Bid Package {bid['pkg']}")
        d.add_paragraph(bid['intro'])
        rows, dec = table_rows(bid)
        has_q = any(r[0] == 'line' and r[3] for r in rows)
        has_up = any(r[0] == 'line' and r[5] for r in rows)
        head = ['Description'] + (['Qty'] if has_q else []) + (['Unit Price'] if has_up else []) + ['Price']
        t = d.add_table(rows=1, cols=len(head))
        t.style = 'Light Grid Accent 1'
        for i, h in enumerate(head):
            t.rows[0].cells[i].text = h
        for r in rows:
            cells = t.add_row().cells
            if r[0] == 'sec':
                m = cells[0].merge(cells[-1])
                m.text = ''
                m.paragraphs[0].add_run(r[1]).bold = True
                continue
            _, n, desc, q, u, up, amt = r
            vals = [desc] + ([f'{q} {u}'.strip()] if has_q else []) + ([up] if has_up else []) + [amt]
            for i, v in enumerate(vals):
                cells[i].text = v
                if i:
                    cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        cells = t.add_row().cells
        cells[0].text, cells[-1].text = 'TOTAL BID', money(bid['total'], dec)
        cells[-1].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.RIGHT
        for cl in (cells[0], cells[-1]):
            cl.paragraphs[0].runs[0].bold = True
        d.add_paragraph()
        if tax_text(bid):
            d.add_paragraph(tax_text(bid))
        for a in bid['alts']:
            d.add_paragraph(f"{a['desc']}: ADD {money(a['amt'], 0)} (not included in the total above)")
        _list(d, 'Our price includes:', bid['incl'])
        _list(d, 'Our price excludes:', bid['excl'])
        _list(d, 'Clarifications:', bid['clar'])
        _list(d, 'Warranty:', bid['warranty'])
        if bid.get('rates'):
            d.add_paragraph().add_run('Hourly rates for extra work (ST / OT / DT):').bold = True
            for k, v in bid['rates']:
                d.add_paragraph(f'{k}: {money(v, 2)} / {money(v * 1.5, 2)} / {money(v * 2, 2)}')
            d.add_paragraph('Markup on changes: ' + ', '.join(f'{k.lower()} {v}' for k, v in bid['markups']))
        tail = []
        if bid['validity']:
            tail.append(f"This bid is good for {bid['validity']} days.")
        if bid['addenda']:
            tail.append('We acknowledge receipt of ' + ', '.join(bid['addenda']) + '.')
        d.add_paragraph(' '.join(tail))
        d.add_paragraph(f"Sincerely,\n\n{c['name']}\n{bid['company']}")
    else:  # short: free-text price lines, no table
        _head(d, bid, 14)
        d.add_paragraph(dt.strftime('%m/%d/%y'))
        d.add_paragraph(bid['intro'])
        _, dec = table_rows(bid)
        for l in bid['lines']:
            amt = money(l['amt'], dec) if isinstance(l['amt'], float) else l['amt']
            if l['up'] is not None:
                s = f"{l['desc']} - {qty_str(l['qty'])} {(l['unit'] or '').lower()} @ {money(l['up'], 2)} = {amt}"
            elif l['qty'] is not None:
                s = f"{l['desc']} - {qty_str(l['qty'])} {(l['unit'] or '').lower()} - {amt}"
            else:
                s = f"{l['desc']} - {amt}"
            d.add_paragraph(s)
        d.add_paragraph().add_run(f"Total {money(bid['total'], dec)}").bold = True
        for a in bid['alts']:
            d.add_paragraph(f"{a['desc']}: add {money(a['amt'], 0)} (not in the total)")
        notes = [f'Does not include {e.lower()}.' for e in bid['excl']] + bid['clar'] + \
                [f'Warranty - {w}.' for w in bid['warranty']] + \
                ([f"Price good {bid['validity']} days."] if bid['validity'] else []) + \
                ([f"We acknowledge {', '.join(bid['addenda'])}."] if bid.get('addenda') else [])
        for nline in notes:
            d.add_paragraph(nline)
        d.add_paragraph(f"Thanks,\n{bid['company']}\n{c['phone']}")
    d.save(str(path))


# ------------------------------------------------------------------ Excel
THIN = Side(style='thin', color='999999')
BOX = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


def _put(ws, ref, v, bold=False, fill=None, color=None, fmt=None, align=None, size=None, font='Calibri', border=False):
    c = ws[ref]
    c.value = v
    c.font = Font(name=font, bold=bold, color=color, size=size or 10)
    if fill:
        c.fill = PatternFill('solid', fgColor=fill)
    if fmt:
        c.number_format = fmt
    if align:
        c.alignment = Alignment(horizontal=align, vertical='top', wrap_text=True)
    if border:
        c.border = BOX
    return c


def _notes(bid):
    out = []
    if tax_text(bid):
        out.append(('Tax', [tax_text(bid)]))
    for title, key in [('Inclusions', 'incl'), ('Exclusions', 'excl'), ('Clarifications', 'clar'), ('Warranty', 'warranty')]:
        if bid[key]:
            out.append((title, bid[key]))
    tail = []
    if bid['validity']:
        tail.append(f"Bid valid for {bid['validity']} days.")
    if bid['addenda']:
        tail.append('Addenda acknowledged: ' + ', '.join(bid['addenda']))
    if tail:
        out.append(('Terms', tail))
    return out


def _rates_sheet(wb, bid, f):
    ws = wb.create_sheet('Alternates & Rates')
    ws.column_dimensions['A'].width = 70
    for col in 'BCD':
        ws.column_dimensions[col].width = 14
    r = 1
    _put(ws, f'A{r}', 'Alternates (not included in base bid)', bold=True, font=f)
    for a in bid['alts']:
        r += 1
        _put(ws, f'A{r}', a['desc'], font=f)
        _put(ws, f'B{r}', a['amt'], fmt='$#,##0', font=f)
    if not bid['alts']:
        r += 1
        _put(ws, f'A{r}', 'None priced', font=f)
    if bid.get('rates'):
        r += 2
        for i, h in enumerate(['Subcontractor Rates', 'Standard', 'OT', 'DT']):
            _put(ws, f'{"ABCD"[i]}{r}', h, bold=True, font=f)
        for k, v in bid['rates']:
            r += 1
            _put(ws, f'A{r}', k, font=f)
            for i, m in enumerate((1, 1.5, 2)):
                _put(ws, f'{"BCD"[i]}{r}', round(v * m, 2), fmt='$#,##0.00', font=f)
        r += 2
        _put(ws, f'A{r}', 'Change Order Rates (Add %)', bold=True, font=f)
        for k, v in bid['markups']:
            r += 1
            _put(ws, f'A{r}', k, font=f)
            _put(ws, f'B{r}', v, font=f, align='right')
    r += 3
    _put(ws, f'A{r}', SYNTH_NOTICE, size=7, color='888888')


def render_xlsx(bid, path):
    wb = Workbook()
    ws = wb.active
    f, acc, c = bid['font'], bid['accent'], bid['contact']
    rows, dec = table_rows(bid)
    mfmt = '$#,##0.00' if dec else '$#,##0'
    if bid['layout'] == 'bidform':
        ws.title = 'Bid Form'
        for col, w in zip('ABCDEFG', (6, 52, 10, 8, 12, 16, 34)):
            ws.column_dimensions[col].width = w
        _put(ws, 'A1', f"{PROJECT['name'].upper()} - BID FORM", bold=True, size=14, font=f)
        _put(ws, 'A2', bid['intro'].replace('Bid Form - ', ''), bold=True, font=f)
        for i, (k, v) in enumerate([('Bidder:', bid['company']), ('Contact:', f"{c['name']}  {c['phone']}  {c['email']}"),
                                    ('Bid date:', bid['date']), ('Bidder reference:', bid['ref'])]):
            _put(ws, f'A{4 + i}', k, bold=True, font=f)
            _put(ws, f'C{4 + i}', v, font=f, fmt='mm/dd/yyyy' if k == 'Bid date:' else None, align='left')
        r = 9
        for i, h in enumerate(['Item', 'BASE BID (bidder\'s proposed value)', 'Qty', 'Unit', 'Unit Price', 'Value', 'Comments']):
            _put(ws, f'{"ABCDEFG"[i]}{r}', h, bold=True, fill=acc, color='FFFFFF', font=f, border=True)
        for row in rows:
            r += 1
            if row[0] == 'sec':
                _put(ws, f'B{r}', row[1], bold=True, fill='DDDDDD', font=f)
                continue
            l = bid['lines'][row[1] - 1]
            _put(ws, f'A{r}', row[1], font=f, border=True)
            _put(ws, f'B{r}', l['desc'], font=f, border=True, align='left')
            _put(ws, f'C{r}', l['qty'], font=f, border=True, fmt='#,##0')
            _put(ws, f'D{r}', (l['unit'] or '').lower() or None, font=f, border=True)
            _put(ws, f'E{r}', l['up'], font=f, border=True, fmt='$#,##0.00')
            _put(ws, f'F{r}', l['amt'], font=f, border=True, fmt=mfmt, align='right')
            _put(ws, f'G{r}', None, border=True)
        r += 2
        _put(ws, f'B{r}', 'BASE BID VALUE', bold=True, font=f)
        _put(ws, f'F{r}', bid['total'], bold=True, fmt=mfmt, font=f, border=True)
        r += 2
        for title, items in _notes(bid):
            _put(ws, f'B{r}', title, bold=True, font=f)
            for it in items:
                r += 1
                _put(ws, f'B{r}', it, font=f, align='left')
            r += 2
        _put(ws, f'A{r + 1}', SYNTH_NOTICE, size=7, color='888888')
        ws.freeze_panes = 'A10'
    else:  # estimate: the sub's own sheet - offset start, merged title, columns in their own order
        ws.title = 'Estimate'
        ws.sheet_view.showGridLines = False
        for col, w in zip('ABCDEF', (3, 58, 16, 10, 8, 4)):
            ws.column_dimensions[col].width = w
        ws.merge_cells('B2:E2')
        _put(ws, 'B2', bid['company'].upper(), bold=True, size=18, color=acc, font=f)
        ws.merge_cells('B3:E3')
        _put(ws, 'B3', f"{c['phone']} | {c['email']}", size=9, font=f)
        _put(ws, 'B5', f"Project: {PROJECT['name']}, {PROJECT['location']}", bold=True, font=f)
        _put(ws, 'B6', bid['intro'], bold=True, color='C00000' if 'REVISED' in bid['intro'] else None, font=f)
        _put(ws, 'B7', f"Date: {bid['date'].strftime('%m/%d/%Y')}     Ref: {bid['ref']}", font=f)
        r = 9
        for i, h in enumerate(['DESCRIPTION', 'AMOUNT', 'QTY', 'UNIT']):
            _put(ws, f'{"BCDE"[i]}{r}', h, bold=True, fill=acc, color='FFFFFF', font=f)
        for row in rows:
            r += 1
            if row[0] == 'sec':
                r += 1
                _put(ws, f'B{r}', row[1].upper(), bold=True, font=f)
                continue
            l = bid['lines'][row[1] - 1]
            _put(ws, f'B{r}', l['desc'], font=f, align='left')
            _put(ws, f'C{r}', l['amt'], font=f, fmt=mfmt, align='right')
            _put(ws, f'D{r}', l['qty'], font=f, fmt='#,##0')
            _put(ws, f'E{r}', l['unit'], font=f)
        r += 2
        _put(ws, f'B{r}', 'TOTAL BID', bold=True, size=12, font=f)
        c_tot = _put(ws, f'C{r}', bid['total'], bold=True, size=12, fmt=mfmt, font=f)
        c_tot.border = Border(top=Side(style='double'))
        r += 2
        for title, items in _notes(bid):
            _put(ws, f'B{r}', title.upper() + ':', bold=True, font=f)
            for it in items:
                r += 1
                _put(ws, f'B{r}', '  - ' + it, font=f, align='left')
            r += 2
        _put(ws, f'B{r + 1}', SYNTH_NOTICE, size=7, color='888888')
    _rates_sheet(wb, bid, f)
    wb.properties.creator = bid['company']
    wb.save(str(path))
