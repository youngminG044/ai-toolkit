from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from uuid import uuid4


class Database:
    def __init__(self, path):
        self.path = Path(path)

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    def initialize(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript('''
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS items (
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, category TEXT NOT NULL,
                    value REAL NOT NULL, status TEXT NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS documents (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, text TEXT NOT NULL, created_at TEXT NOT NULL);
            ''')

    def items(self, limit=100, offset=0):
        with self.connect() as db:
            total = db.execute('SELECT COUNT(*) FROM items').fetchone()[0]
            rows = db.execute('SELECT * FROM items ORDER BY created_at DESC, id LIMIT ? OFFSET ?', (limit, offset)).fetchall()
        return {'items': [dict(row) for row in rows], 'total': total, 'limit': limit, 'offset': offset}

    def create_item(self, data):
        item = {'id': str(uuid4()), **data, 'created_at': datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            db.execute('INSERT INTO items VALUES (:id,:title,:category,:value,:status,:created_at)', item)
        return item

    def update_item(self, identifier, data):
        with self.connect() as db:
            db.execute('UPDATE items SET title=:title,category=:category,value=:value,status=:status WHERE id=:id',
                       {'id': identifier, **data})
            row = db.execute('SELECT * FROM items WHERE id=?', (identifier,)).fetchone()
        return dict(row) if row else None

    def delete(self, table, identifier):
        if table not in {'items', 'documents'}:
            raise ValueError('unknown table')
        with self.connect() as db:
            return db.execute(f'DELETE FROM {table} WHERE id=?', (identifier,)).rowcount > 0

    def documents(self, include_text=False):
        columns = 'id,name,text,created_at' if include_text else 'id,name,created_at,length(text) AS characters'
        with self.connect() as db:
            return [dict(row) for row in db.execute(f'SELECT {columns} FROM documents ORDER BY created_at,id').fetchall()]

    def add_document(self, name, text):
        document = {'id': str(uuid4()), 'name': name, 'text': text, 'created_at': datetime.now(timezone.utc).isoformat()}
        with self.connect() as db:
            # A write transaction serializes the limit check and insert.
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM documents').fetchone()[0] >= 50:
                raise ValueError('document limit reached (50)')
            db.execute('INSERT INTO documents VALUES (:id,:name,:text,:created_at)', document)
        return {k: v for k, v in document.items() if k != 'text'}
