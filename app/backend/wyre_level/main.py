"""HTTP API for the Wyre bid leveling POC."""
import re
from pathlib import Path

from fastapi import Body, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config, db, engine, export, ingest, llm, seed
from .pipeline import extract, policy as policy_mod, run as runner

app = FastAPI(title='Wyre bid leveling')


@app.on_event('startup')
def _startup():
    db.conn()
    seed.seed()


def _pkg(pid):
    p = db.one('SELECT * FROM packages WHERE id=?', (pid,))
    if not p:
        raise HTTPException(404, 'Package not found')
    return p


def _pkg_meta(p, docs=None):
    docs = docs if docs is not None else db.many('SELECT id, kind, status FROM documents WHERE package_id=?', (p['id'],))
    res = p.get('result')
    rec = next((b for b in res['bidders'] if b['id'] == res.get('recommendedId')), None) if res else None
    return {'id': p['id'], 'projectId': p['project_id'], 'code': p['code'], 'name': p['name'], 'lastLeveledAt': p['last_leveled_at'],
            'bids': sum(1 for d in docs if d['kind'] == 'bid'), 'documents': len(docs), 'scopeItems': len((p.get('scope') or {}).get('items') or []),
            'hasPolicy': bool(p.get('policy')), 'leveled': len(res['bidders']) if res else 0, 'qualified': res['summary']['qualified'] if res else 0,
            'recommended': rec['name'] if rec else None, 'recommendedTotal': rec['leveledTotal'] if rec else None, 'run': runner.status(p['id'])}


@app.get('/api/health')
def health():
    return {'ok': True, 'llm': llm.available(), 'model': config.GEMINI_MODEL, 'stats': llm.stats}


# ---------------------------------------------------------------- projects and packages
@app.get('/api/projects')
def projects():
    out = []
    for pr in db.many('SELECT * FROM projects ORDER BY created_at'):
        pk = db.many('SELECT * FROM packages WHERE project_id=? ORDER BY code', (pr['id'],))
        out.append({'id': pr['id'], 'name': pr['name'], 'location': pr['location'], 'packages': [_pkg_meta(p) for p in pk]})
    return out


@app.post('/api/projects')
def create_project(body: dict = Body(...)):
    pid = db.new_id('p_')
    db.insert('projects', id=pid, name=body.get('name') or 'New project', location=body.get('location') or '', created_at=db.now())
    return {'id': pid}


@app.post('/api/projects/{project_id}/packages')
def create_package(project_id: str, body: dict = Body(...)):
    kid = db.new_id('k_')
    db.insert('packages', id=kid, project_id=project_id, code=body.get('code') or '00.00', name=body.get('name') or 'New bid package', created_at=db.now(),
              scope=None, policy=None, settings={'ai_text': True}, result=None, run=None, last_leveled_at=None)
    return {'id': kid}


@app.get('/api/packages/{pid}')
def package(pid: str):
    p = _pkg(pid)
    pr = db.one('SELECT * FROM projects WHERE id=?', (p['project_id'],))
    return {**_pkg_meta(p), 'project': {'id': pr['id'], 'name': pr['name'], 'location': pr['location']}}


# ---------------------------------------------------------------- scope (baseline items)
@app.get('/api/packages/{pid}/scope')
def get_scope(pid: str):
    return _pkg(pid).get('scope') or {'items': []}


@app.put('/api/packages/{pid}/scope')
def put_scope(pid: str, body: dict = Body(...)):
    _pkg(pid)
    items, seen = [], set()
    for it in body.get('items') or []:
        key = re.sub(r'[^A-Z0-9_]', '', str(it.get('key') or '').upper())[:12] or f'ITEM{len(items) + 1}'
        while key in seen:
            key += 'X'
        seen.add(key)
        unit = (it.get('unit') or 'LS').upper()
        qty = float(it['qty']) if it.get('qty') not in (None, '') and unit != 'LS' else None
        est = float(it['estimate']) if it.get('estimate') not in (None, '') else None
        rate = float(it['rate']) if it.get('rate') not in (None, '') else (round(est / qty, 4) if est and qty else None)
        if est is None and rate and qty:
            est = round(rate * qty, 2)
        items.append({'key': key, 'name': it.get('name') or key, 'section': it.get('section') or 'General', 'unit': unit, 'qty': qty, 'rate': rate,
                      'estimate': est, 'depth': float(it['depth']) if it.get('depth') not in (None, '') else None, 'spec': it.get('spec')})
    db.update('packages', pid, scope={'items': items})
    return {'items': items}


@app.post('/api/packages/{pid}/scope/generate')
def generate_scope(pid: str):
    _pkg(pid)
    doc = db.one("SELECT * FROM documents WHERE package_id=? AND kind='scope_sheet' ORDER BY uploaded_at DESC", (pid,))
    if not doc:
        raise HTTPException(400, 'Upload a scope sheet first')
    try:
        token = llm.stage_models.set((_pkg(pid).get('settings') or {}).get('stage_models', {}))
        try:
            items = extract.extract_scope(doc['path'])
        finally:
            llm.stage_models.reset(token)
    except llm.LLMError as e:
        raise HTTPException(502, f'The model could not read the scope sheet: {e}')
    db.update('packages', pid, scope={'items': items})
    return {'items': items, 'source': doc['filename']}


# ---------------------------------------------------------------- documents
def _doc_out(d, full=False):
    ext = d.get('extraction') or {}
    out = {'id': d['id'], 'kind': d['kind'], 'filename': d['filename'], 'mime': d['mime'], 'size': d['size'], 'uploadedAt': d['uploaded_at'],
           'status': d['status'], 'error': d['error'], 'hasFile': bool(d.get('path')),
           'bidder': ext.get('bidder_name'), 'docType': ext.get('doc_type'), 'bidDate': ext.get('bid_date'), 'statedTotal': ext.get('stated_total'),
           'linesTotal': ext.get('lines_total'), 'checks': ext.get('checks') or [], 'isRevision': ext.get('is_revision')}
    if full:
        out['extraction'] = ext or None
    return out


@app.get('/api/packages/{pid}/documents')
def documents(pid: str):
    return [_doc_out(d) for d in db.many('SELECT * FROM documents WHERE package_id=? ORDER BY uploaded_at', (pid,))]


@app.get('/api/documents/{did}')
def document(did: str):
    d = db.one('SELECT * FROM documents WHERE id=?', (did,))
    if not d:
        raise HTTPException(404, 'Document not found')
    return _doc_out(d, full=True)


@app.post('/api/packages/{pid}/documents')
async def upload(pid: str, file: UploadFile = File(...), kind: str = Form('')):
    _pkg(pid)
    name = Path(file.filename or 'upload').name
    did = db.new_id('d_')
    dest = config.UPLOADS / did
    dest.mkdir(parents=True, exist_ok=True)
    data = await file.read()
    (dest / name).write_bytes(data)
    db.insert('documents', id=did, package_id=pid, kind=kind or seed.kind_of(name), filename=name, path=str(dest / name), mime=ingest.mime_of(name),
              size=len(data), uploaded_at=db.now(), status='uploaded', error=None, extraction=None)
    return _doc_out(db.one('SELECT * FROM documents WHERE id=?', (did,)))


@app.patch('/api/documents/{did}')
def patch_document(did: str, body: dict = Body(...)):
    if body.get('kind') in ('bid', 'award_policy', 'plug_policy', 'scope_sheet', 'supporting'):
        db.update('documents', did, kind=body['kind'])
    return _doc_out(db.one('SELECT * FROM documents WHERE id=?', (did,)))


@app.delete('/api/documents/{did}')
def delete_document(did: str):
    db.delete('documents', did)
    return {'ok': True}


@app.get('/api/documents/{did}/file')
def document_file(did: str):
    d = db.one('SELECT * FROM documents WHERE id=?', (did,))
    if not d or not d.get('path') or not Path(d['path']).exists():
        raise HTTPException(404, 'No file stored for this document')
    return FileResponse(d['path'], media_type=d['mime'], filename=d['filename'], content_disposition_type='inline')


# ---------------------------------------------------------------- policy (ordinals) and plug settings
@app.get('/api/packages/{pid}/policy')
def get_policy(pid: str):
    p = _pkg(pid)
    doc = db.one("SELECT filename FROM documents WHERE package_id=? AND kind='award_policy' ORDER BY filename", (pid,))
    return {'policy': p.get('policy'), 'settings': engine.merged_settings(p.get('settings')) | {'ai_text': (p.get('settings') or {}).get('ai_text', True)},
            'methods': engine.METHOD_LABEL, 'policyDocument': doc['filename'] if doc else None,
            'items': [{'key': i['key'], 'name': i['name']} for i in (p.get('scope') or {}).get('items') or []]}


@app.post('/api/packages/{pid}/policy/generate')
def gen_policy(pid: str):
    _pkg(pid)
    token = llm.stage_models.set((_pkg(pid).get('settings') or {}).get('stage_models', {}))
    try:
        return {'policy': runner.generate_policy(pid)}
    finally:
        llm.stage_models.reset(token)


@app.put('/api/packages/{pid}/policy')
def put_policy(pid: str, body: dict = Body(...)):
    _pkg(pid)
    pol = policy_mod.normalize(body['policy'])
    pol['source'] = 'edited' if body['policy'].get('source') in ('ai', 'edited') else body['policy'].get('source', 'edited')
    db.update('packages', pid, policy=pol)
    return {'policy': pol}


@app.put('/api/packages/{pid}/settings')
def put_settings(pid: str, body: dict = Body(...)):
    p = _pkg(pid)
    if 'stage_models' in body:
        import os
        allowed = {config.GEMINI_MODEL, os.getenv('GEMINI_HIGHER_MODEL'), os.getenv('GEMINI_HIGHEST_MODEL')}
        routes = body['stage_models']
        if not isinstance(routes, dict) or any(not isinstance(m, str) or m not in allowed for m in routes.values()):
            raise HTTPException(400, 'Choose configured Gemini model IDs.')
    s = {**(p.get('settings') or {}), **{k: v for k, v in body.items() if k in ('threshold_pct', 'ai_auto', 'ai_web_search', 'ai_text', 'default', 'items', 'allowances', 'stage_models')}}
    db.update('packages', pid, settings=s)
    return {'settings': engine.merged_settings(s) | {'ai_text': s.get('ai_text', True)}}


# ---------------------------------------------------------------- leveling
@app.post('/api/packages/{pid}/level')
def level(pid: str, body: dict = Body(default={})):
    _pkg(pid)
    return runner.start(pid, force_extract=bool(body.get('forceExtract')))


@app.get('/api/packages/{pid}/run')
def run_status(pid: str):
    return runner.status(pid) or {'status': 'idle'}


@app.get('/api/packages/{pid}/result')
def result(pid: str):
    p = _pkg(pid)
    if not p.get('result'):
        raise HTTPException(404, 'This package has not been leveled yet')
    r = p['result']
    r['overrides'] = db.many('SELECT * FROM overrides WHERE package_id=? ORDER BY created_at', (pid,))
    return r


@app.get('/api/packages/{pid}/overrides')
def overrides(pid: str):
    return db.many('SELECT * FROM overrides WHERE package_id=? ORDER BY created_at', (pid,))


@app.post('/api/packages/{pid}/overrides')
def add_override(pid: str, body: dict = Body(...)):
    _pkg(pid)
    act = body.get('action')
    if act not in ('manual_value', 'include', 'exclude', 'plug', 'reset'):
        raise HTTPException(400, 'Unknown override action')
    with db._lock:      # one override per cell: the newest replaces the old one
        db.conn().execute('DELETE FROM overrides WHERE package_id=? AND bidder_id=? AND item_key=?', (pid, body['bidderId'], body['itemKey']))
        db.conn().commit()
    if act != 'reset':
        payload = {k: body[k] for k in ('value', 'method', 'amount', 'note') if body.get(k) not in (None, '')}
        db.insert('overrides', id=db.new_id('o_'), package_id=pid, bidder_id=body['bidderId'], item_key=body['itemKey'], action=act, payload=payload, created_at=db.now())
    return runner.start(pid)


@app.get('/api/packages/{pid}/export.xlsx')
def export_xlsx(pid: str):
    p = _pkg(pid)
    if not p.get('result'):
        raise HTTPException(404, 'This package has not been leveled yet')
    name = re.sub(r'[^A-Za-z0-9._-]+', '_', f"{p['code']}_{p['name']}_leveled.xlsx")
    return Response(export.build(p['result']), media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    headers={'Content-Disposition': f'attachment; filename="{name}"'})


# ---------------------------------------------------------------- built front end, when present
_dist = config.REPO / 'app' / 'frontend' / 'dist'
if _dist.exists():
    app.mount('/assets', StaticFiles(directory=_dist / 'assets'), name='assets')

    @app.get('/{path:path}')
    def spa(path: str):
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / 'index.html')
