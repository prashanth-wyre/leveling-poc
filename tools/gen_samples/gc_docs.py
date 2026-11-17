"""GC-side inputs: project brief, awarding policy, prequal roster, clarification log, scope sheets."""
from docx import Document
from docx.shared import Pt
from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill

from model import SYNTH_NOTICE
from specs import CLARIFICATIONS, PACKAGES, PREQUAL, PROJECT
from tcjc import shift

HDR = PatternFill('solid', fgColor='1F2937')
SYN = 'SYNTHETIC'
WBK = 'TCJC workbook'


def cmgc(s):
    return s.replace("DPR's", "CM/GC's").replace('DPR', 'CM/GC')


def sheet(wb, title, head, widths, first=False):
    ws = wb.active if first else wb.create_sheet()
    ws.title = title
    ws.append(head)
    for i, w in enumerate(widths):
        ws.column_dimensions[chr(65 + i)].width = w
        c = ws.cell(row=1, column=i + 1)
        c.font, c.fill = Font(bold=True, color='FFFFFF'), HDR
        c.alignment = Alignment(wrap_text=True, vertical='top')
    ws.freeze_panes = 'A2'
    return ws


def wrap(ws):
    for row in ws.iter_rows(min_row=2):
        for c in row:
            c.alignment = Alignment(wrap_text=True, vertical='top')


def facts(wb):
    es, data = wb.tab('Estimate Summary'), wb.tab('Data')
    return dict(gsf=es.num('H', 9), sdi_rate=data.num('C', 3), title=es.text('C', 1), phase=es.text('C', 2))


def textura_rate(pkgs):
    """Textura fee / base bid, which is constant across the three tabs."""
    rates = set()
    for p in pkgs.values():
        t, k = p['tab'], p['k']
        for b, _ in p['bidders']:
            fee, base = t.money(shift(b, 4), k['textura']), t.money(shift(b, 4), k['base'])
            if fee and base:
                rates.add(round(fee / base, 6))
    assert max(rates) - min(rates) < 2e-6, rates
    return sorted(rates)[0]


def alternates(pkg):
    t, k = pkg['tab'], pkg['k']
    return [t.text('C', r) for r in range(k['alt'] + 1, k['allow']) if t.text('C', r)]


def policy_sections(f, trate, pkgs):
    wmin = []
    for p in pkgs.values():
        wmin += [f"{p['code']} {p['name']} - {item}: {term}." for item, term in p['warranty_min']]
    return [
        ('1. Purpose', [
            'This policy sets out how subcontract bid packages for the Teton County Justice Center are leveled and awarded. '
            'It applies to every trade package bid at the 90% Construction Documents stage.']),
        ('2. Basis of award', [
            'Award is recommended to the lowest responsive and responsible bidder, measured on Leveled Total Package Value, not on the price as submitted.',
            'Leveled Total Package Value = bid as submitted + CM/GC plugs for scope gaps = Base Bid Value; + post-bid adjustments (Textura) = Subcontract Value; + sales tax and SDI = Total Package Value.',
            'A bidder within 3% of the lowest leveled total may be recommended instead on best-value grounds (schedule, warranty, safety, staffing) with written justification from the package lead.']),
        ('3. Responsive bids', [
            'A bid is responsive if it was received by the bid deadline, is priced against the current documents including all addenda, and the bidder answers CM/GC clarification questions within two (2) business days.',
            'Clarification questions are sent to the bidders the package lead considers in contention for award. They are recorded in the bid clarification log. A bidder who was not sent questions remains responsive.',
            'A bidder that does not answer clarification questions by the deadline is marked UNRESPONSIVE and is excluded from award, whatever its price.',
            'When a bidder submits more than one bid, only the latest dated bid is leveled. Earlier bids are kept on file as superseded.',
            'Bids are requested to remain valid for 60 days. A shorter validity is flagged but does not make a bid non-responsive.']),
        ('4. Responsible bidders', [
            'The recommended bidder must hold prequalification status "Approved" or "Approved with conditions" at award. Conditions must be closed in writing before the subcontract is issued.',
            'The Total Package Value may not exceed the bidder\'s single-project limit on the prequalification roster.',
            'Predicted Safety Incidents score: 5.0 or below is acceptable; above 5.0 and up to 15.0 requires a safety mitigation plan; above 15.0 requires written approval from the regional safety manager before award.']),
        ('5. Leveling rules', [
            'Scope gaps: where a bidder excludes or omits a scope item, the CM/GC adds a plug. The plug is the CM/GC estimate for that item or, where another bidder priced the same item, that bidder\'s price.',
            'Allowances the CM/GC carries for every bidder (for example additional flashing, touch-ups after other trades) are added to all bidders equally.',
            'An item marked "included" by the bidder may still receive a plug where the CM/GC judges the included scope to be insufficient. Such plugs are recorded as contingency.',
            'Sales tax: the project is tax exempt. Bids are leveled exclusive of sales tax. Where a bidder includes tax and gives a breakout, the tax is deducted. Where no breakout is given the bid is carried as submitted and flagged. Where a bidder quotes sales tax outside its total, the tax is carried under Insurance and Tax until the exemption for that material is confirmed under Exhibit 27.',
            f'Textura: a payment-system fee of {trate * 100:.3f}% of Base Bid Value is added to each bidder as a post-bid adjustment.',
            f'Subcontractor Default Insurance (SDI): {f["sdi_rate"] * 100:.2f}% of Subcontract Value is added for each SDI-enrolled bidder. Bidders not enrolled in SDI provide a payment and performance bond instead.',
            'Quantities: bidder quantities are compared to the CM/GC takeoff. A difference above 10% on any item is flagged for clarification.',
            'Arithmetic: where line extensions or totals do not add up, the error is flagged. The bid is carried as written until the bidder confirms a correction.']),
        ('6. Low-bid review', [
            'A scope review is mandatory for any bid whose Leveled Total Package Value is more than 20% below the CM/GC estimate, or more than 15% below the next lowest bidder.']),
        ('7. Warranty minimums', [
            'Bidders must meet the warranties in the contract documents. Minimums for the packages in this sample set:'] + wmin + [
            'A warranty shortfall must be corrected in writing before award. If the bidder will not correct it, the cost of an equivalent warranty is added as a plug.']),
        ('8. Alternates', [
            'Alternates are not part of the leveled comparison. They are reported separately for each bidder.']),
        ('9. Combination and all-or-nothing bids', [
            'A bidder who will not allow its price to be split across packages is flagged. The bid may still be recommended where the whole of its price falls in one package.']),
        ('10. Approval', [
            'Recommendations up to $250,000 are approved by the project manager; from $250,000 to $1,000,000 by the project executive; above $1,000,000 by the regional preconstruction lead with Owner concurrence.']),
    ]


def write_policy(out, f, trate, pkgs, sec5=None):
    secs = policy_sections(f, trate, pkgs)
    if sec5:
        secs[4] = (secs[4][0], sec5)
    note = ('SYNTHETIC TEST DOCUMENT. Written for bid-leveling POC testing. It is not the actual policy of any contractor. '
            'The rules are chosen to be consistent with the awards recorded in the TCJC leveling workbook.')
    d = Document()
    d.styles['Normal'].font.size = Pt(10.5)
    d.add_heading('Subcontract Award Policy', 0)
    d.add_paragraph(f"{PROJECT['name']} - {f['phase']}")
    d.add_paragraph(note).runs[0].italic = True
    md = ['# Subcontract Award Policy', '', f"{PROJECT['name']} - {f['phase']}", '', f'> {note}', '']
    for title, paras in secs:
        d.add_heading(title, 1)
        md += [f'## {title}', '']
        for i, p in enumerate(paras, 1):
            n = f"{title.split('.')[0]}.{i}"
            d.add_paragraph(f'{n}  {p}')
            md += [f'**{n}** {p}', '']
    d.save(str(out / 'awarding_policy.docx'))
    (out / 'awarding_policy.md').write_text('\n'.join(md))


def write_brief(out, f, trate, pkgs):
    alts = alternates(next(iter(pkgs.values())))
    L = [f"# {PROJECT['name']} - project brief for bidders", '',
         '> Project facts are from the TCJC workbook. Dates, the addendum and the bid address are SYNTHETIC.', '',
         f"- Project: {PROJECT['name']}, {PROJECT['location']}",
         f"- Documents: {f['phase']}",
         f"- Building gross area: {f['gsf']:,.0f} SF",
         '- Delivery: CM/GC. Bids are submitted to the CM/GC, who levels them and recommends an award.',
         '- The project is tax exempt (see Exhibit 27 - Tax Exempt Process).',
         f"- Subcontractor Default Insurance (SDI) at {f['sdi_rate'] * 100:.2f}% of subcontract value.",
         f'- Textura payment system; fee of {trate * 100:.3f}% of base bid value.',
         '- LEED Silver requirements apply.',
         f"- Invitation to bid issued: {PROJECT['rfp_issued']}",
         f"- Addendum 01 issued: {PROJECT['addendum1']} (roofing: electronic leak detection per Section 07 54 23 confirmed in base bid; "
         'acoustic flute filler at roof deck is supplied by the steel deck subcontractor and installed by the roofer)',
         f"- Bids due: {PROJECT['bid_due']}, 2:00 PM Mountain Time",
         '- Clarification responses due within two business days of the question.', '',
         '## Bid packages in this sample set', '']
    L += [f"- {p['code']} {p['name']}" for p in pkgs.values()]
    L += ['', '## Project alternates (price separately, not in base bid)', ''] + [f'- {a}' for a in alts]
    (out / 'project_brief.md').write_text('\n'.join(L) + '\n')


def write_prequal(out, pkgs):
    wb = Workbook()
    ws = sheet(wb, 'Prequalification', ['Subcontractor', 'Bid package', 'Prequalification status', 'Single-project limit ($)',
                                        'Predicted Safety Incidents', 'SDI enrolled', 'Source of safety score'],
               [36, 30, 38, 18, 16, 12, 30], first=True)
    for p in pkgs.values():
        t = p['tab']
        for b, name in p['bidders']:
            status, limit, sdi = PREQUAL[name]
            score = t.num(shift(b, 4), 8)
            ws.append([name, f"{p['code']} {p['name']}", status, limit, score if score is not None else 'Not on file',
                       'Yes' if sdi else 'No', WBK + ' row 8' if score is not None else 'n/a'])
            ws.cell(row=ws.max_row, column=4).number_format = '$#,##0'
    ws.append([])
    ws.append(['Status, limits and SDI enrolment are SYNTHETIC. Predicted Safety Incidents scores are from the TCJC workbook where shown.'])
    wb.save(str(out / 'subcontractor_prequal.xlsx'))


def write_clarifications(out, pkgs):
    wb = Workbook()
    ws = sheet(wb, 'Clarification Log', ['Bid package', 'Bidder', 'Question sent', 'Question', 'Response due',
                                         'Response received', 'Response summary'], [26, 32, 14, 60, 14, 16, 60], first=True)
    for code, name, sent, q, resp, summary in CLARIFICATIONS:
        ws.append([f"{code} {pkgs[code]['name']}", name, sent, q, PROJECT['bid_due'].replace(day=21), resp or 'NO RESPONSE', summary])
    wrap(ws)
    ws.append([])
    ws.append(['SYNTHETIC log. Who was questioned and who did not respond is consistent with the workbook notes ("?s sent", "scoped", "UNRESPONSIVE").'])
    wb.save(str(out / 'bid_clarification_log.xlsx'))


def write_scope_sheet(out, pkg):
    t, k, eb = pkg['tab'], pkg['k'], pkg['est_block']
    q, u, p, v = (shift(eb, i) for i in (1, 2, 3, 4))
    wb = Workbook()
    ws = sheet(wb, 'Scope Items', ['No.', 'Scope item', 'Type', 'CM/GC quantity (90% CD)', 'Unit', 'Bidder Qty', 'Bidder Unit',
                                   'Bidder Unit Price', 'Bidder Value', 'Comments'], [6, 64, 12, 16, 8, 12, 12, 16, 16, 30], first=True)
    n = 0
    for r in pkg['scope_price'] + pkg['scope_confirm']:
        n += 1
        kind = 'Price' if r in pkg['scope_price'] else 'Confirm'
        unit = t.text(u, r)
        ws.append([n, cmgc(t.text('C', r)), kind, t.num(q, r), unit.strip('.') if unit else None])
    for r in pkg['spec_rows']:
        ws.append([None, 'Specification section: ' + ' '.join(t.text('C', r).split())])
    ws.append([])
    ws.append(['', 'Price every "Price" item. For "Confirm" items state Included / Excluded. List anything else under Comments.'])
    wrap(ws)

    ws = sheet(wb, 'Bid Form Requirements', ['Ref', 'Requirement', 'Section'], [8, 80, 40])
    for a, b, title in [(k['pba'], k['subvalue'], 'Post-bid adjustments - confirm included'),
                        (k['ctc'], k['total'], 'Costs to complete - confirm included'),
                        (k['alt'], k['allow'], 'Alternates - price separately'),
                        (k['ack'], k['div'], 'Bid document acknowledgements')]:
        for r in range(a + 1, b):
            ref, c = t.num('B', r), t.text('C', r)
            if ref is None or not c or c.lower().startswith(('exhibit xx', 'a2 completed')):
                continue
            ws.append([f'{ref:.2f}', cmgc(c), title])
    for i, req in enumerate(['Labor rates: General Foreman, Foreman, Journeyman, Apprentice (standard / OT / DT)',
                             'Change order mark-ups: labor, material, equipment, first-tier subcontractors (add and deduct %)',
                             'Unit prices for added or deleted work', 'Lower-tier subcontractors and suppliers',
                             'Warranty offered for each system (see Required Warranties)', 'Bid validity: 60 days'], 1):
        ws.append([f'R{i}', req, 'Other bid evaluation criteria'])
    wrap(ws)

    ws = sheet(wb, 'Required Warranties', ['System', 'Minimum warranty', 'Source'], [50, 80, 14])
    for item, term in pkg['warranty_min']:
        ws.append([item, term, SYN])
    wrap(ws)

    ws = sheet(wb, 'CMGC Estimate (confidential)', ['Estimate line (DD estimate)', 'Qty', 'Unit', 'Unit price', 'Value'],
               [60, 12, 8, 14, 16])
    a, b = pkg['est_rows']
    for r in range(a, b + 1):
        if t.text('C', r):
            unit = t.text(u, r)
            ws.append([t.text('C', r), t.num(q, r), unit.strip('.') if unit else None, t.money(p, r), t.money(v, r)])
    ws.append(['TOTAL CM/GC ESTIMATE', None, None, None, pkg['estimate']])
    for row in ws.iter_rows(min_row=2):
        row[3].number_format = row[4].number_format = '$#,##0.00'
    ws.append([])
    ws.append(['Not issued to bidders. Used as the baseline for variance and for pricing scope-gap plugs.'])
    d = out / pkg['slug']
    d.mkdir(parents=True, exist_ok=True)
    wb.save(str(d / 'scope_sheet.xlsx'))
