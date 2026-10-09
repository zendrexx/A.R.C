"""Local SQLite evidence store. Project paths are explicitly registered."""

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path):
        self.path = path.expanduser().resolve()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.connection = sqlite3.connect(self.path)
        os.chmod(self.path, 0o600)
        self.connection.row_factory = sqlite3.Row
        self.connection.execute("PRAGMA foreign_keys = ON")
        self.connection.executescript("""
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
                test_command TEXT, created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS tasks (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                title TEXT NOT NULL, claim TEXT, confirmed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                task_id TEXT REFERENCES tasks(id), kind TEXT NOT NULL,
                summary TEXT NOT NULL, source TEXT NOT NULL, source_ref TEXT NOT NULL,
                git_head TEXT, fingerprint TEXT, details_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS events_project_time ON events(project_id, created_at);
            CREATE TABLE IF NOT EXISTS vectors (
                event_id TEXT PRIMARY KEY REFERENCES events(id), model TEXT NOT NULL,
                values_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                fingerprint TEXT NOT NULL, payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(event_id UNINDEXED, summary);
        """)
        self.connection.commit()

    def close(self) -> None:
        self.connection.close()

    def register_project(self, path: Path, test_command: str | None = None) -> dict:
        path = path.expanduser().resolve()
        if not path.is_dir():
            raise ValueError(f"Project folder does not exist: {path}")
        existing = self.get_project(path)
        if existing:
            if test_command is not None:
                self.connection.execute("UPDATE projects SET test_command=? WHERE id=?",
                                        (test_command, existing["id"]))
                self.connection.commit()
            return self.get_project(path)
        project_id = uuid4().hex
        self.connection.execute(
            "INSERT INTO projects VALUES (?, ?, ?, ?, ?)",
            (project_id, str(path), path.name, test_command, utc_now()),
        )
        self.connection.commit()
        return self.get_project(path)

    def get_project(self, path_or_id: Path | str) -> dict | None:
        if isinstance(path_or_id, Path):
            value = str(path_or_id.expanduser().resolve())
        else:
            value = path_or_id
        row = self.connection.execute(
            "SELECT * FROM projects WHERE path=? OR id=?", (value, value)
        ).fetchone()
        return dict(row) if row else None

    def add_task(self, project_id: str, title: str) -> dict:
        task_id = uuid4().hex[:12]
        self.connection.execute(
            "INSERT INTO tasks VALUES (?, ?, ?, NULL, 0, ?)",
            (task_id, project_id, title.strip(), utc_now()),
        )
        self.connection.commit()
        return self.get_task(task_id)

    def get_task(self, task_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM tasks WHERE id=?", (task_id,)).fetchone()
        return dict(row) if row else None

    def tasks(self, project_id: str) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM tasks WHERE project_id=? ORDER BY created_at, id", (project_id,)
        )]

    def set_claim(self, task_id: str, claim: str) -> None:
        self.connection.execute("UPDATE tasks SET claim=? WHERE id=?", (claim, task_id))
        self.connection.commit()

    def confirm_task(self, task_id: str) -> None:
        self.connection.execute("UPDATE tasks SET confirmed=1 WHERE id=?", (task_id,))
        self.connection.commit()

    def add_event(self, project_id: str, kind: str, summary: str, source: str,
                  source_ref: str, task_id: str | None = None, git_head: str | None = None,
                  fingerprint: str | None = None, details: dict | None = None) -> dict:
        event_id = uuid4().hex
        if source_ref == "auto":
            source_ref = f"arc:event/{event_id}"
        self.connection.execute(
            """INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, project_id, task_id, kind, summary, source, source_ref,
             git_head, fingerprint, json.dumps(details or {}), utc_now()),
        )
        self.connection.execute("INSERT INTO event_fts (event_id, summary) VALUES (?, ?)",
                                (event_id, summary))
        self.connection.commit()
        return self.get_event(event_id)

    def get_event(self, event_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return self._event(row) if row else None

    @staticmethod
    def _event(row: sqlite3.Row) -> dict:
        value = dict(row)
        value["details"] = json.loads(value.pop("details_json"))
        return value

    def events(self, project_id: str, limit: int = 50, task_id: str | None = None) -> list[dict]:
        if task_id:
            rows = self.connection.execute(
                "SELECT * FROM events WHERE project_id=? AND task_id=? ORDER BY rowid DESC LIMIT ?",
                (project_id, task_id, limit),
            )
        else:
            rows = self.connection.execute(
                "SELECT * FROM events WHERE project_id=? ORDER BY rowid DESC LIMIT ?",
                (project_id, limit),
            )
        return [self._event(row) for row in rows]

    def pending_embeddings(self, project_id: str, model: str) -> list[dict]:
        rows = self.connection.execute("""
            SELECT e.* FROM events e LEFT JOIN vectors v
            ON e.id=v.event_id AND v.model=?
            WHERE e.project_id=? AND v.event_id IS NULL ORDER BY e.rowid
        """, (model, project_id))
        return [self._event(row) for row in rows]

    def put_vector(self, event_id: str, model: str, values: list[float]) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO vectors VALUES (?, ?, ?)",
            (event_id, model, json.dumps(values, allow_nan=False)),
        )
        self.connection.commit()

    def vectors(self, project_id: str, model: str) -> list[tuple[dict, list[float]]]:
        rows = self.connection.execute("""
            SELECT e.*, v.values_json FROM events e JOIN vectors v ON e.id=v.event_id
            WHERE e.project_id=? AND v.model=? ORDER BY e.rowid DESC
        """, (project_id, model))
        result = []
        for row in rows:
            event = self._event(row)
            values = json.loads(event.pop("values_json"))
            result.append((event, values))
        return result

    def keyword_search(self, project_id: str, query: str, limit: int) -> list[dict]:
        tokens = re.findall(r"[\w]+", query, flags=re.UNICODE)[:10]
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens)
        rows = self.connection.execute("""
            SELECT e.* FROM event_fts f JOIN events e ON e.id=f.event_id
            WHERE e.project_id=? AND event_fts MATCH ? ORDER BY bm25(event_fts) LIMIT ?
        """, (project_id, expression, limit))
        return [self._event(row) for row in rows]

    def save_checkpoint(self, project_id: str, fingerprint: str, payload: dict) -> dict:
        checkpoint_id = uuid4().hex[:12]
        created_at = utc_now()
        self.connection.execute(
            "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
            (checkpoint_id, project_id, fingerprint, json.dumps(payload), created_at),
        )
        self.connection.commit()
        return {"id": checkpoint_id, "project_id": project_id, "fingerprint": fingerprint,
                "payload": payload, "created_at": created_at}

    def latest_checkpoint(self, project_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM checkpoints WHERE project_id=? ORDER BY rowid DESC LIMIT 1",
            (project_id,),
        ).fetchone()
        if not row:
            return None
        result = dict(row)
        result["payload"] = json.loads(result.pop("payload_json"))
        return result
