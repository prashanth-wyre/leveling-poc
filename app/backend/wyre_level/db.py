"""SQLite storage. Each package keeps its scope, policy, settings and last result as JSON documents."""
import json
import sqlite3
import threading
import time
import uuid

from .config import DB_PATH

_lock = threading.RLock()
_conn = None

SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT, location TEXT, created_at REAL);
CREATE TABLE IF NOT EXISTS packages (
  id TEXT PRIMARY KEY, project_id TEXT, code TEXT, name TEXT, created_at REAL,
  scope TEXT, policy TEXT, settings TEXT, result TEXT, run TEXT, last_leveled_at REAL);
CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY, package_id TEXT, kind TEXT, filename TEXT, path TEXT, mime TEXT, size INTEGER,
  uploaded_at REAL, status TEXT, error TEXT, extraction TEXT);
CREATE TABLE IF NOT EXISTS overrides (
  id TEXT PRIMARY KEY, package_id TEXT, bidder_id TEXT, item_key TEXT, action TEXT, payload TEXT, created_at REAL);
"""
JSON_COLS = {'scope', 'policy', 'settings', 'result', 'run', 'extraction', 'payload'}


def conn():
    global _conn
    with _lock:
        if _conn is None:
            _conn = sqlite3.connect(DB_PATH, check_same_thread=False)
            _conn.row_factory = sqlite3.Row
            _conn.executescript(SCHEMA)
        return _conn


def new_id(prefix=''):
    return prefix + uuid.uuid4().hex[:10]


def _row(r):
    if r is None:
        return None
    d = dict(r)
    for k in JSON_COLS & d.keys():
        d[k] = json.loads(d[k]) if d[k] else None
    return d


def one(sql, args=()):
    with _lock:
        return _row(conn().execute(sql, args).fetchone())


def many(sql, args=()):
    with _lock:
        return [_row(r) for r in conn().execute(sql, args).fetchall()]


def insert(table, **vals):
    vals = {k: json.dumps(v) if k in JSON_COLS and v is not None else v for k, v in vals.items()}
    with _lock:
        conn().execute(f"INSERT INTO {table} ({','.join(vals)}) VALUES ({','.join('?' * len(vals))})", list(vals.values()))
        conn().commit()


def update(table, id, **vals):
    vals = {k: json.dumps(v) if k in JSON_COLS and v is not None else v for k, v in vals.items()}
    with _lock:
        conn().execute(f"UPDATE {table} SET {','.join(k + '=?' for k in vals)} WHERE id=?", [*vals.values(), id])
        conn().commit()


def delete(table, id):
    with _lock:
        conn().execute(f'DELETE FROM {table} WHERE id=?', (id,))
        conn().commit()


def now():
    return time.time()
