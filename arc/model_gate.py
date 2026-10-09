"""Serialize local model calls across processes sharing an A.R.C. database."""
import time
from contextlib import contextmanager
from uuid import uuid4


@contextmanager
def model_slot(store):
    from arc.memory import EmbeddingUnavailable
    db = store.connection
    db.execute('CREATE TABLE IF NOT EXISTS model_lease (id INTEGER PRIMARY KEY, owner TEXT NOT NULL, expires REAL NOT NULL)')
    db.commit()
    owner = uuid4().hex
    db.execute('BEGIN IMMEDIATE')
    db.execute('DELETE FROM model_lease WHERE expires<?', (time.time(),))
    available = db.execute('INSERT OR IGNORE INTO model_lease VALUES (1, ?, ?)',
                           (owner, time.time() + 90)).rowcount
    db.commit()
    if not available:
        raise EmbeddingUnavailable('Another local model request is active; use recorded keyword evidence or retry.')
    try:
        yield
    finally:
        db.execute('DELETE FROM model_lease WHERE owner=?', (owner,))
        db.commit()
