"""Stdlib-only reader for the TCJC leveling workbook (cached cell values only)."""
import re
import zipfile
import xml.etree.ElementTree as ET

M = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
R = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'


def col2n(c):
    n = 0
    for ch in c:
        n = n * 26 + ord(ch) - 64
    return n


def n2col(n):
    s = ''
    while n:
        n, r = divmod(n - 1, 26)
        s = chr(65 + r) + s
    return s


def shift(col, k):
    return n2col(col2n(col) + k)


class Tab(dict):
    """Cells keyed by A1 reference. Numbers are floats, text is stripped str."""

    rows = ()

    def v(self, col, row):
        return self.get(f'{col}{row}')

    def num(self, col, row):
        x = self.v(col, row)
        return x if isinstance(x, float) else None

    def money(self, col, row):
        x = self.num(col, row)
        return None if x is None else round(x, 2)

    def text(self, col, row):
        x = self.v(col, row)
        return x if isinstance(x, str) else None


class Workbook:
    def __init__(self, path):
        self.z = zipfile.ZipFile(path)
        self.ss = [''.join(t.text or '' for t in si.iter(M + 't'))
                   for si in ET.fromstring(self.z.read('xl/sharedStrings.xml'))]
        wb = ET.fromstring(self.z.read('xl/workbook.xml'))
        rels = {r.get('Id'): r.get('Target')
                for r in ET.fromstring(self.z.read('xl/_rels/workbook.xml.rels'))}
        self.paths = {s.get('name'): 'xl/' + rels[s.get(R + 'id')] for s in wb.find(M + 'sheets')}

    def tab(self, name):
        t = Tab()
        rows = set()
        root = ET.fromstring(self.z.read(self.paths[name]))
        for c in root.iter(M + 'c'):
            v = c.find(M + 'v')
            if v is None or v.text is None:
                continue
            ty = c.get('t')
            if ty == 's':
                val = self.ss[int(v.text)].strip()
            elif ty in ('str', 'e', 'inlineStr'):
                val = v.text.strip()
            else:
                val = float(v.text)
            if val == '':
                continue
            t[c.get('r')] = val
            rows.add(int(re.sub(r'[A-Z]+', '', c.get('r'))))
        t.rows = sorted(rows)
        return t


def key_rows(tab):
    """Locate the summary rows of a Bid Tally Sheet tab by their labels."""
    k = {}
    for r in tab.rows:
        b, c = tab.v('B', r), tab.v('C', r)
        bn = round(b, 2) if isinstance(b, float) else None
        cs = c if isinstance(c, str) else ''
        if cs == 'BASE BID VALUE':
            k['base'] = r
        elif cs == 'SUBCONTRACT VALUE':
            k['subvalue'] = r
        elif cs.startswith('TOTAL PACKAGE VALUE'):
            k['total'] = r
        elif bn == 2.01 and cs == 'Textura':
            k['textura'] = r
        elif bn == 4.01:
            k['tax'] = r
        elif bn == 4.02:
            k['sdi'] = r
        elif isinstance(b, str) and 'RECOMMENDED BIDDER' in b:
            k['rec'] = r
        elif bn == 2 and cs.startswith('POST BID'):
            k['pba'] = r
        elif bn == 5 and cs.startswith('COSTS TO COMPLETE'):
            k['ctc'] = r
        elif bn == 7 and cs.startswith('Alternate Pricing'):
            k['alt'] = r
        elif bn == 8 and cs.startswith('Allowances'):
            k['allow'] = r
        elif bn == 13 and cs.startswith('Bid Document'):
            k['ack'] = r
        elif bn == 14 and cs.startswith('Diversity'):
            k['div'] = r
    return k


BLOCKS = ['D', 'I', 'N', 'S', 'X', 'AC', 'AH']


def bidders(tab, est_block):
    """[(block start col, company name)] for the bidder blocks left of the estimate block."""
    out = []
    for b in BLOCKS:
        if col2n(b) >= col2n(est_block):
            break
        name = tab.text(b, 2)
        if name:
            out.append((b, name))
    return out
