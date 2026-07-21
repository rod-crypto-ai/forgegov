from __future__ import annotations
import json, os, sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

DB_PATH = Path(os.getenv('FORGEGOV_DB', 'forgegov.db'))

@contextmanager
def connection() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys=ON')
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()

def init_db() -> None:
    with connection() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS opportunities(
          notice_id TEXT PRIMARY KEY, title TEXT NOT NULL, solicitation_number TEXT,
          agency TEXT, office TEXT, naics TEXT, set_aside TEXT, posted_date TEXT,
          response_deadline TEXT, place_of_performance TEXT, description TEXT,
          url TEXT, raw_json TEXT NOT NULL, updated_at TEXT DEFAULT CURRENT_TIMESTAMP);
        CREATE TABLE IF NOT EXISTS pipeline(
          id INTEGER PRIMARY KEY AUTOINCREMENT, notice_id TEXT NOT NULL,
          stage TEXT NOT NULL DEFAULT 'New', owner TEXT, estimated_value REAL DEFAULT 0,
          probability INTEGER DEFAULT 10, due_date TEXT, notes TEXT DEFAULT '',
          incumbent_json TEXT DEFAULT '{}', created_at TEXT DEFAULT CURRENT_TIMESTAMP,
          updated_at TEXT DEFAULT CURRENT_TIMESTAMP, UNIQUE(notice_id));
        CREATE TABLE IF NOT EXISTS saved_searches(
          id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, query_json TEXT NOT NULL,
          alerts_enabled INTEGER DEFAULT 0, created_at TEXT DEFAULT CURRENT_TIMESTAMP);
        ''')

def upsert_opportunity(o: dict[str, Any]) -> None:
    with connection() as c:
        c.execute('''INSERT INTO opportunities(notice_id,title,solicitation_number,agency,office,naics,set_aside,posted_date,response_deadline,place_of_performance,description,url,raw_json)
        VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?) ON CONFLICT(notice_id) DO UPDATE SET
        title=excluded.title, solicitation_number=excluded.solicitation_number, agency=excluded.agency,
        office=excluded.office, naics=excluded.naics, set_aside=excluded.set_aside,
        posted_date=excluded.posted_date, response_deadline=excluded.response_deadline,
        place_of_performance=excluded.place_of_performance, description=excluded.description,
        url=excluded.url, raw_json=excluded.raw_json, updated_at=CURRENT_TIMESTAMP''',
        (o['notice_id'],o['title'],o.get('solicitation_number'),o.get('agency'),o.get('office'),o.get('naics'),o.get('set_aside'),o.get('posted_date'),o.get('response_deadline'),o.get('place_of_performance'),o.get('description'),o.get('url'),json.dumps(o.get('raw',{}))))

def add_to_pipeline(notice_id: str, stage: str='New') -> None:
    with connection() as c:
        c.execute('INSERT INTO pipeline(notice_id,stage) VALUES(?,?) ON CONFLICT(notice_id) DO NOTHING',(notice_id,stage))

def update_pipeline(record_id: int, **fields: Any) -> None:
    allowed={'stage','owner','estimated_value','probability','due_date','notes','incumbent_json'}
    clean={k:v for k,v in fields.items() if k in allowed}
    if not clean: return
    sets=', '.join(f'{k}=?' for k in clean)+', updated_at=CURRENT_TIMESTAMP'
    with connection() as c:
        c.execute(f'UPDATE pipeline SET {sets} WHERE id=?',(*clean.values(),record_id))

def pipeline_rows() -> list[dict[str,Any]]:
    with connection() as c:
        rows=c.execute('''SELECT p.*,o.title,o.solicitation_number,o.agency,o.naics,o.set_aside,o.response_deadline,o.url
        FROM pipeline p JOIN opportunities o ON o.notice_id=p.notice_id ORDER BY p.updated_at DESC''').fetchall()
    return [dict(r) for r in rows]

def save_search(name: str, query: dict[str,Any], alerts: bool=False) -> None:
    with connection() as c:
        c.execute('INSERT INTO saved_searches(name,query_json,alerts_enabled) VALUES(?,?,?)',(name,json.dumps(query),int(alerts)))

def saved_searches() -> list[dict[str,Any]]:
    with connection() as c: rows=c.execute('SELECT * FROM saved_searches ORDER BY created_at DESC').fetchall()
    out=[]
    for r in rows:
        d=dict(r); d['query']=json.loads(d.pop('query_json')); out.append(d)
    return out
