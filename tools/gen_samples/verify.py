"""Independent checks on the generated files: re-read each one from disk and compare."""
import re

from docx import Document
from openpyxl import load_workbook
from pypdf import PdfReader

from model import SYNTH_NOTICE, near
from tcjc import shift


def text_of(path):
    """Return (text, numbers) extracted from a generated file."""
    nums = []
    if path.suffix == '.pdf':
        txt = '\n'.join(p.extract_text() for p in PdfReader(str(path)).pages)
    elif path.suffix == '.docx':
        d = Document(str(path))
        parts = [p.text for p in d.paragraphs]
        parts += [c.text for t in d.tables for row in t.rows for c in row.cells]
        parts += [p.text for s in d.sections for p in s.footer.paragraphs]
        txt = '\n'.join(parts)
    else:
        parts = []
        for ws in load_workbook(str(path), data_only=True):
            for row in ws.iter_rows(values_only=True):
                for v in row:
                    if isinstance(v, (int, float)):
                        nums.append(float(v))
                    elif v is not None:
                        parts.append(str(v))
        txt = '\n'.join(parts)
    for m in re.findall(r'\(?\$?\d[\d,]*\.?\d*\)?', txt):
        s = m.strip('()$').replace(',', '')
        if s and s != '.':
            try:
                nums.append(-float(s) if m.startswith('(') else float(s))
            except ValueError:
                pass
    return txt, nums


def check_files(files):
    bad = []
    for b, path in files:
        if not path.exists() or path.stat().st_size < 1000:
            bad.append(f'{path.name}: missing or empty')
            continue
        txt, nums = text_of(path)
        if 'SYNTHETIC TEST DATA' not in txt:
            bad.append(f'{path.name}: synthetic notice not found')
        if b['company'].lower() not in txt.lower():
            bad.append(f'{path.name}: company name not found')
        if 'lines' not in b:
            continue
        want = [b['total']] + [l['amt'] for l in b['lines'] if isinstance(l['amt'], float)] + [a['amt'] for a in b['alts']]
        for w in want:
            if not any(near(w, n) for n in nums):
                bad.append(f'{path.name}: amount {w} not found in file')
    return bad


def run(files, keys, pkgs):
    bad = check_files(files)
    # Answer key vs workbook cells, read again directly.
    for c, key in keys.items():
        t, k = pkgs[c]['tab'], pkgs[c]['k']
        for e in key['bidders']:
            b = e['workbook_block']
            if e['status'] == 'declined':
                if t.money(shift(b, 4), k['base']):
                    bad.append(f"{c} {e['company']}: marked declined but workbook has a base bid")
                continue
            for field, cell in [('base_bid_value', (shift(b, 4), k['base'])), ('subcontract_value', (b, k['subvalue'])),
                                ('total_package_value', (b, k['total']))]:
                if not near(e[field], t.money(*cell)):
                    bad.append(f"{c} {e['company']}: {field} {e[field]} != workbook {t.money(*cell)}")
            # Every numeric workbook cell in the scope section must be accounted for as a bid line or a plug.
            used = {l['workbook_row'] for l in e['lines'] if isinstance(l['amount'], float)} | {g['row'] for g in e['gc_plugs']}
            for r in range(pkgs[c]['scope_start'], k['base']):
                v = t.money(shift(b, 4), r)
                is_subtotal = t.num('B', r) is None and t.num(b, r) is None and c == '32.90' and t.text('C', r) in (
                    'Site Furnishings', 'Landscape', 'Irrigation System', 'Paving and Surfacing', 'General')
                if v and r not in used and not is_subtotal:
                    bad.append(f"{c} {e['company']}: workbook row {r} ({t.text('C', r)}) = {v} not used")
        if key['recommended_bidder'] != next(n for b, n in pkgs[c]['bidders'] if t.text(b, k['rec']) == n):
            bad.append(f'{c}: recommended bidder mismatch')
    return bad
