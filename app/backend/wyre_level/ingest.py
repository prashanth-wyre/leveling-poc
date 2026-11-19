"""Turn an uploaded file into something the model can read: PDFs go in as files, Word and Excel as text."""
import mimetypes
from pathlib import Path

MIME = {
    '.pdf': 'application/pdf',
    '.docx': 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
    '.xlsx': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    '.xlsm': 'application/vnd.ms-excel.sheet.macroEnabled.12',
    '.md': 'text/markdown', '.txt': 'text/plain', '.yaml': 'text/yaml', '.yml': 'text/yaml', '.csv': 'text/csv',
}


def mime_of(name):
    return MIME.get(Path(name).suffix.lower()) or mimetypes.guess_type(name)[0] or 'application/octet-stream'


def _docx_text(path):
    from docx import Document
    d = Document(str(path))
    out = []
    # body order matters for a bid letter: walk paragraphs and tables in document order
    body = d.element.body
    paras = {p._p: p for p in d.paragraphs}
    tables = {t._tbl: t for t in d.tables}
    for child in body.iterchildren():
        if child in paras:
            t = paras[child].text.strip()
            if t:
                out.append(t)
        elif child in tables:
            for row in tables[child].rows:
                cells, seen = [], set()
                for c in row.cells:           # merged cells repeat; keep the first occurrence
                    if c._tc in seen:
                        continue
                    seen.add(c._tc)
                    cells.append(c.text.strip().replace('\n', ' '))
                out.append(' | '.join(cells))
    return '\n'.join(out)


def _xlsx_text(path, max_rows=400, max_cols=40):
    from openpyxl import load_workbook
    wb = load_workbook(str(path), data_only=True, read_only=True)
    out = []
    try:
        for ws in wb.worksheets:
            if ws.sheet_state != 'visible':
                continue
            out.append(f'## Sheet: {ws.title}')
            for r, row in enumerate(ws.iter_rows(values_only=True), 1):
                if r > max_rows:
                    out.append('... (rows truncated)')
                    break
                cells = []
                for c, v in enumerate(row[:max_cols], 1):
                    if v is None or v == '':
                        continue
                    if hasattr(v, 'strftime'):
                        v = v.strftime('%Y-%m-%d')
                    elif isinstance(v, float):
                        v = f'{v:.4f}'.rstrip('0').rstrip('.')
                    col = ''
                    n = c
                    while n:
                        n, rem = divmod(n - 1, 26)
                        col = chr(65 + rem) + col
                    cells.append(f'{col}{r}={v}')
                if cells:
                    out.append(' | '.join(cells))
    finally:
        # read_only workbooks keep the file open until closed; Windows then blocks moving the folder (WinError 32)
        wb.close()
    return '\n'.join(out)


def _pdf_text(path):
    try:
        from pypdf import PdfReader
        return '\n'.join((p.extract_text() or '') for p in PdfReader(str(path)).pages)
    except Exception:
        return ''


def read(path):
    """Returns {'files': [(mime, bytes)], 'text': str}. `files` is non-empty only where the model should see the
    original (PDF); `text` is always filled where it can be, for prompts and for finding source snippets."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == '.pdf':
        return {'files': [('application/pdf', path.read_bytes())], 'text': _pdf_text(path)}
    if ext == '.docx':
        return {'files': [], 'text': _docx_text(path)}
    if ext in ('.xlsx', '.xlsm'):
        return {'files': [], 'text': _xlsx_text(path)}
    return {'files': [], 'text': path.read_text(errors='replace')}
