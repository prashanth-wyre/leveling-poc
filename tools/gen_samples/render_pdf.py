"""PDF bids (reportlab): 'proposal', 'quote' and 'email' layouts."""
from xml.sax.saxutils import escape as esc

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from model import SYNTH_NOTICE, money, table_rows, tax_text
from specs import PROJECT

BOLD = {'Helvetica': 'Helvetica-Bold', 'Times-Roman': 'Times-Bold', 'Courier': 'Courier-Bold'}
W = letter[0] - 1.5 * inch


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont('Helvetica', 6.5)
    canvas.setFillColor(colors.grey)
    canvas.drawString(0.75 * inch, 0.45 * inch, SYNTH_NOTICE)
    canvas.drawRightString(letter[0] - 0.75 * inch, 0.45 * inch, f'Page {doc.page}')
    canvas.restoreState()


def _styles(bid, size):
    f, fb = bid['font'], BOLD[bid['font']]
    acc = colors.HexColor(bid['accent'])
    return dict(
        n=ParagraphStyle('n', fontName=f, fontSize=size, leading=size * 1.35),
        b=ParagraphStyle('b', fontName=fb, fontSize=size, leading=size * 1.35),
        r=ParagraphStyle('r', fontName=f, fontSize=size, leading=size * 1.35, alignment=TA_RIGHT),
        h=ParagraphStyle('h', fontName=fb, fontSize=size + 1.5, leading=size * 1.6, textColor=acc, spaceBefore=9, spaceAfter=3),
        big=ParagraphStyle('big', fontName=fb, fontSize=20, leading=24, textColor=acc),
        small=ParagraphStyle('s', fontName=f, fontSize=size - 1.5, leading=size * 1.2, textColor=colors.HexColor('#444444')),
    ), acc, f, fb


def _bullets(story, st, title, items, numbered=False):
    if not items:
        return
    story.append(Paragraph(esc(title), st['h']))
    for i, it in enumerate(items, 1):
        mark = f'{i}.' if numbered else '-'
        story.append(Paragraph(f'{mark}&nbsp;&nbsp;{esc(it)}', st['n']))


def _price_table(bid, st, acc, f, fb, size, total_label):
    rows, dec = table_rows(bid)
    has_q = any(r[0] == 'line' and r[3] for r in rows)
    has_up = any(r[0] == 'line' and r[5] for r in rows)
    head = ['Item', 'Description'] + (['Qty', 'Unit'] if has_q else []) + (['Unit Price'] if has_up else []) + ['Amount']
    ncol = len(head)
    data, style = [head], [
        ('FONTNAME', (0, 0), (-1, -1), f), ('FONTNAME', (0, 0), (-1, 0), fb), ('FONTSIZE', (0, 0), (-1, -1), size),
        ('BACKGROUND', (0, 0), (-1, 0), acc), ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'), ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('LINEBELOW', (0, 0), (-1, -1), 0.25, colors.HexColor('#BBBBBB')),
    ]
    for r in rows:
        if r[0] == 'sec':
            data.append([Paragraph(esc(r[1]), st['b'])] + [''] * (ncol - 1))
            i = len(data) - 1
            style += [('SPAN', (0, i), (-1, i)), ('BACKGROUND', (0, i), (-1, i), colors.HexColor('#EEEEEE'))]
        else:
            _, n, desc, q, u, up, amt = r
            data.append([str(n), Paragraph(esc(desc), st['n'])] + ([q, u] if has_q else []) + ([up] if has_up else []) + [amt])
    data.append(['', Paragraph(esc(total_label), st['b'])] + [''] * (ncol - 3) + [money(bid['total'], dec)])
    style += [('FONTNAME', (0, len(data) - 1), (-1, len(data) - 1), fb),
              ('LINEABOVE', (0, len(data) - 1), (-1, len(data) - 1), 1, colors.black)]
    fixed = [0.4 * inch] + ([0.7 * inch, 0.5 * inch] if has_q else []) + ([0.85 * inch] if has_up else []) + [1.15 * inch]
    widths = [fixed[0], W - sum(fixed)] + fixed[1:]
    t = Table(data, colWidths=widths, repeatRows=1)
    t.setStyle(TableStyle(style))
    return t, dec


def _alts(story, bid, st, fb, size):
    if not bid['alts']:
        return
    story.append(Paragraph('Alternates (not included in base bid)', st['h']))
    data = [[Paragraph(esc(a['desc']), st['n']), 'ADD ' + money(a['amt'], 0)] for a in bid['alts']]
    t = Table(data, colWidths=[W - 1.3 * inch, 1.3 * inch])
    t.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), size), ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                           ('VALIGN', (0, 0), (-1, -1), 'TOP'), ('BOX', (0, 0), (-1, -1), 0.25, colors.grey)]))
    story.append(t)


def _rates(story, bid, st, size):
    if not bid.get('rates'):
        return
    story.append(Paragraph('Labor Rates and Change Order Markups', st['h']))
    data = [['Classification', 'Straight time', 'Overtime', 'Double time']]
    data += [[c, money(v, 2), money(v * 1.5, 2), money(v * 2, 2)] for c, v in bid['rates']]
    t = Table(data, colWidths=[2.2 * inch, 1.2 * inch, 1.2 * inch, 1.2 * inch], hAlign='LEFT')
    t.setStyle(TableStyle([('FONTSIZE', (0, 0), (-1, -1), size), ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
                           ('GRID', (0, 0), (-1, -1), 0.25, colors.grey), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold')]))
    story += [t, Spacer(1, 4),
              Paragraph(esc('Change order markup: ' + '; '.join(f'{k} {v}' for k, v in bid['markups'])), st['n'])]


def _closing(story, bid, st):
    bits = []
    if bid['validity']:
        bits.append(f"This proposal is valid for {bid['validity']} days from the date above.")
    if bid['addenda']:
        bits.append('Addenda acknowledged: ' + ', '.join(bid['addenda']) + '.')
    if bits:
        story += [Spacer(1, 8), Paragraph(esc(' '.join(bits)), st['n'])]
    c = bid['contact']
    story += [Spacer(1, 16), Paragraph('Respectfully submitted,', st['n']), Spacer(1, 22),
              Paragraph(esc(f"{c['name']}, {bid['company']}"), st['b']),
              Paragraph(esc(f"{c['phone']}  |  {c['email']}"), st['small'])]


def render_pdf(bid, path):
    doc = SimpleDocTemplate(str(path), pagesize=letter, leftMargin=0.75 * inch, rightMargin=0.75 * inch,
                            topMargin=0.7 * inch, bottomMargin=0.8 * inch, title=bid['file'], author=bid['company'])
    c, story = bid['contact'], []
    dt = bid['date']
    if bid['layout'] == 'email':
        st, acc, f, fb = _styles(bid, 10)
        for k, v in [('From', f"{bid['company']} <{c['email']}>"), ('Sent', dt.strftime('%A, %B %d, %Y') + ' 4:12 PM'),
                     ('To', 'CM/GC Preconstruction <bids@cmgc.example>'),
                     ('Subject', f"RE: {PROJECT['short']} {bid['pkg']} {bid.get('pkg_name', 'Roofing')} - invitation to bid")]:
            story.append(Paragraph(f'<b>{k}:</b> {esc(v)}', st['n']))
        story.append(Spacer(1, 14))
        for p in bid['body']:
            story += [Paragraph(esc(p), st['n']), Spacer(1, 8)]
        story += [Paragraph(esc(bid['company']), st['n']), Paragraph(esc(c['phone']), st['n'])]
    elif bid['layout'] == 'proposal':
        size = 9.5
        st, acc, f, fb = _styles(bid, size)
        band = Table([[Paragraph(esc(bid['company']), ParagraphStyle('band', fontName=fb, fontSize=17, leading=20, textColor=colors.white)),
                       Paragraph(f'<font color="white" size="8.5">{esc(c["phone"])}<br/>{esc(c["email"])}</font>', st['r'])]],
                     colWidths=[W * 0.5, W * 0.5])
        band.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, -1), acc), ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                                  ('TOPPADDING', (0, 0), (-1, -1), 12), ('BOTTOMPADDING', (0, 0), (-1, -1), 12)]))
        story += [band, Spacer(1, 12),
                  Paragraph(esc(f"{dt.strftime('%B %d, %Y')}  |  Proposal No. {bid['ref']}"), st['n']), Spacer(1, 8),
                  Paragraph('To: CM/GC Preconstruction and Estimating', st['n']),
                  Paragraph(esc(f"Project: {PROJECT['name']}, {PROJECT['location']}"), st['b']),
                  Paragraph(esc(f"Re: Bid Package {bid['pkg']}"), st['b']), Spacer(1, 8),
                  Paragraph(esc(bid['intro']), st['n']), Paragraph('Base Bid', st['h'])]
        t, dec = _price_table(bid, st, acc, f, fb, size, 'TOTAL BASE BID')
        story.append(t)
        tx = tax_text(bid)
        if tx:
            story += [Spacer(1, 5), Paragraph(esc(tx), st['b'] if bid['tax'] == 'add' else st['n'])]
        _alts(story, bid, st, fb, size)
        _bullets(story, st, 'Inclusions', bid['incl'])
        _bullets(story, st, 'Exclusions', bid['excl'])
        _bullets(story, st, 'Clarifications and Qualifications', bid['clar'], numbered=True)
        _bullets(story, st, 'Warranty', bid['warranty'])
        _rates(story, bid, st, size - 1)
        _closing(story, bid, st)
    else:  # quote
        size = 10
        st, acc, f, fb = _styles(bid, size)
        box = Table([['QUOTE'], [f"No. {bid['ref']}"], [dt.strftime('%m/%d/%Y')]], colWidths=[1.6 * inch])
        box.setStyle(TableStyle([('FONTNAME', (0, 0), (0, 0), fb), ('FONTNAME', (0, 1), (0, -1), f), ('FONTSIZE', (0, 0), (0, 0), 14),
                                 ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('BOX', (0, 0), (-1, -1), 1, acc)]))
        head = Table([[[Paragraph(esc(bid['company']), st['big']), Paragraph(esc(f"{c['phone']}  {c['email']}"), st['small'])], box]],
                     colWidths=[W - 1.7 * inch, 1.7 * inch])
        head.setStyle(TableStyle([('VALIGN', (0, 0), (-1, -1), 'TOP')]))
        story += [head, Spacer(1, 14), Paragraph(esc(f"Job: {PROJECT['name']} - {PROJECT['location']}"), st['b']),
                  Paragraph(esc(bid['intro']), st['n']), Spacer(1, 10)]
        t, dec = _price_table(bid, st, acc, f, fb, size, 'TOTAL')
        story.append(t)
        notes = ([tax_text(bid)] if tax_text(bid) else []) + bid['incl'] + bid['clar'] + \
                [f'Not included: {e}' for e in bid['excl']] + [f'Warranty: {w}' for w in bid['warranty']] + \
                [f"{a['desc']}: add {money(a['amt'], 0)}" for a in bid['alts']] + \
                ([f"Quote good for {bid['validity']} days."] if bid['validity'] else []) + \
                (['Acknowledge ' + ', '.join(bid['addenda']) + '.'] if bid['addenda'] else [])
        _bullets(story, st, 'Notes', notes, numbered=True)
        story += [Spacer(1, 24), Paragraph('Accepted by: ______________________     Date: ____________', st['n'])]
    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
