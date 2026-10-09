"""Local SQLite evidence store. Project paths are explicitly registered."""

import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

SEARCH_STOPWORDS = frozenset({
    "a", "an", "and", "are", "at", "be", "because", "by", "could", "did",
    "do", "does", "for", "from", "how", "in", "is", "it", "of", "on",
    "our", "the", "their", "this", "to", "was", "were", "what", "when",
    "where", "why", "with", "would",
})


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
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                label TEXT NOT NULL, started_at TEXT NOT NULL, ended_at TEXT
            );
            CREATE UNIQUE INDEX IF NOT EXISTS sessions_one_active_per_project
                ON sessions(project_id) WHERE ended_at IS NULL;
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
            CREATE TABLE IF NOT EXISTS incidents (
                id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
                error_event_id TEXT NOT NULL UNIQUE REFERENCES events(id),
                cause TEXT, cause_event_id TEXT REFERENCES events(id),
                created_at TEXT NOT NULL, resolved_at TEXT
            );
            CREATE INDEX IF NOT EXISTS incidents_project_time
                ON incidents(project_id, created_at);
            CREATE TABLE IF NOT EXISTS incident_links (
                id TEXT PRIMARY KEY, incident_id TEXT NOT NULL REFERENCES incidents(id),
                event_id TEXT NOT NULL REFERENCES events(id),
                role TEXT NOT NULL CHECK(role IN ('attempt', 'resolution', 'test')),
                outcome TEXT, created_at TEXT NOT NULL,
                UNIQUE(incident_id, event_id)
            );
            CREATE INDEX IF NOT EXISTS incident_links_incident
                ON incident_links(incident_id, created_at);
            CREATE UNIQUE INDEX IF NOT EXISTS incident_one_resolution
                ON incident_links(incident_id) WHERE role='resolution';
            CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(event_id UNINDEXED, summary);
        """)
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(events)")}
        if "session_id" not in columns:
            self.connection.execute(
                "ALTER TABLE events ADD COLUMN session_id TEXT REFERENCES sessions(id)"
            )
        incident_columns = {row["name"] for row in self.connection.execute(
            "PRAGMA table_info(incidents)"
        )}
        if "cause_event_id" not in incident_columns:
            self.connection.execute(
                "ALTER TABLE incidents ADD COLUMN cause_event_id TEXT REFERENCES events(id)"
            )
        self.connection.execute(
            "CREATE INDEX IF NOT EXISTS events_session ON events(session_id)"
        )
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

    def active_session(self, project_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE project_id=? AND ended_at IS NULL",
            (project_id,),
        ).fetchone()
        return dict(row) if row else None

    def start_session(self, project_id: str, label: str) -> dict:
        if self.active_session(project_id):
            raise ValueError("A session is already active. End it before starting another.")
        session_id = uuid4().hex[:12]
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, NULL)",
            (session_id, project_id, label, utc_now()),
        )
        self.connection.commit()
        return self.get_session(session_id)

    def end_session(self, project_id: str) -> dict:
        active = self.active_session(project_id)
        if not active:
            raise ValueError("No active session to end")
        self.connection.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?",
            (utc_now(), active["id"]),
        )
        self.connection.commit()
        return self.get_session(active["id"])

    def get_session(self, session_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM sessions WHERE id=?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def sessions(self, project_id: str, limit: int = 20) -> list[dict]:
        return [dict(row) for row in self.connection.execute(
            "SELECT * FROM sessions WHERE project_id=? ORDER BY rowid DESC LIMIT ?",
            (project_id, limit),
        )]

    def session_events(self, project_id: str, session_id: str, limit: int = 100) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM events WHERE project_id=? AND session_id=? ORDER BY rowid LIMIT ?",
            (project_id, session_id, limit),
        )
        return [self._event(row) for row in rows]

    def session_event_count(self, project_id: str, session_id: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM events WHERE project_id=? AND session_id=?",
            (project_id, session_id),
        ).fetchone()
        return int(row[0])

    def set_claim(self, task_id: str, claim: str) -> None:
        self.connection.execute("UPDATE tasks SET claim=? WHERE id=?", (claim, task_id))
        self.connection.commit()

    def add_event(self, project_id: str, kind: str, summary: str, source: str,
                  source_ref: str, task_id: str | None = None, git_head: str | None = None,
                  fingerprint: str | None = None, details: dict | None = None,
                  set_task_confirmed: bool | None = None) -> dict:
        if set_task_confirmed is not None and not task_id:
            raise ValueError("A task status change must name a task")
        event_id = uuid4().hex
        if source_ref == "auto":
            source_ref = f"arc:event/{event_id}"
        active = self.active_session(project_id)
        with self.connection:
            if set_task_confirmed is not None:
                self.connection.execute(
                    "UPDATE tasks SET confirmed=? WHERE id=? AND project_id=?",
                    (int(set_task_confirmed), task_id, project_id),
                )
            self.connection.execute(
                """INSERT INTO events
                   (id, project_id, task_id, kind, summary, source, source_ref,
                    git_head, fingerprint, details_json, created_at, session_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, project_id, task_id, kind, summary, source, source_ref,
                 git_head, fingerprint, json.dumps(details or {}), utc_now(),
                 active["id"] if active else None),
            )
            self.connection.execute("INSERT INTO event_fts (event_id, summary) VALUES (?, ?)",
                                    (event_id, summary))
        return self.get_event(event_id)

    def get_event(self, event_id: str) -> dict | None:
        row = self.connection.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        return self._event(row) if row else None

    def event_is_newer(self, candidate_id: str, reference_id: str) -> bool:
        row = self.connection.execute(
            """SELECT (SELECT rowid FROM events WHERE id=?) >
                      (SELECT rowid FROM events WHERE id=?)""",
            (candidate_id, reference_id),
        ).fetchone()
        return bool(row[0])

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

    def task_event_count(self, project_id: str, task_id: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM events WHERE project_id=? AND task_id=?",
            (project_id, task_id),
        ).fetchone()
        return int(row[0])

    def project_event_count(self, project_id: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM events WHERE project_id=?", (project_id,)
        ).fetchone()
        return int(row[0])

    def create_incident(self, project_id: str, error_event_id: str,
                        cause: str | None = None,
                        cause_event_id: str | None = None) -> dict:
        incident_id = uuid4().hex[:12]
        self.connection.execute(
            """INSERT INTO incidents
               (id, project_id, error_event_id, cause, cause_event_id, created_at, resolved_at)
               VALUES (?, ?, ?, ?, ?, ?, NULL)""",
            (incident_id, project_id, error_event_id, cause, cause_event_id, utc_now()),
        )
        self.connection.commit()
        return self.get_incident(incident_id)

    def get_incident(self, incident_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM incidents WHERE id=?", (incident_id,)
        ).fetchone()
        return dict(row) if row else None

    def incident_for_error(self, project_id: str, error_event_id: str) -> dict | None:
        row = self.connection.execute(
            "SELECT * FROM incidents WHERE project_id=? AND error_event_id=?",
            (project_id, error_event_id),
        ).fetchone()
        return dict(row) if row else None

    def set_incident_cause(self, incident_id: str, cause: str, event_id: str) -> None:
        self.connection.execute(
            "UPDATE incidents SET cause=?, cause_event_id=? WHERE id=?",
            (cause, event_id, incident_id),
        )
        self.connection.commit()

    def incidents(self, project_id: str, limit: int = 100) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM incidents WHERE project_id=? ORDER BY rowid DESC LIMIT ?",
            (project_id, limit),
        )
        return [dict(row) for row in rows]

    def incident_links(self, incident_id: str) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM incident_links WHERE incident_id=? ORDER BY rowid",
            (incident_id,),
        )
        return [dict(row) for row in rows]

    def link_incident_event(self, incident_id: str, event_id: str, role: str,
                            outcome: str | None = None) -> dict:
        link_id = uuid4().hex
        created_at = utc_now()
        with self.connection:
            self.connection.execute(
                "INSERT INTO incident_links VALUES (?, ?, ?, ?, ?, ?)",
                (link_id, incident_id, event_id, role, outcome, created_at),
            )
            if role == "resolution":
                self.connection.execute(
                    "UPDATE incidents SET resolved_at=? WHERE id=?",
                    (created_at, incident_id),
                )
        return {"id": link_id, "incident_id": incident_id, "event_id": event_id,
                "role": role, "outcome": outcome, "created_at": created_at}

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

    def vectors(self, project_id: str, model: str,
                kind: str | None = None) -> list[tuple[dict, list[float]]]:
        rows = self.connection.execute("""
            SELECT e.*, v.values_json FROM events e JOIN vectors v ON e.id=v.event_id
            WHERE e.project_id=? AND v.model=? AND (? IS NULL OR e.kind=?)
            ORDER BY e.rowid DESC
        """, (project_id, model, kind, kind))
        result = []
        for row in rows:
            event = self._event(row)
            values = json.loads(event.pop("values_json"))
            result.append((event, values))
        return result

    def index_counts(self, project_id: str, model: str,
                     kind: str | None = None) -> dict[str, int]:
        row = self.connection.execute("""
            SELECT COUNT(*) AS total, COUNT(v.event_id) AS indexed
            FROM events e LEFT JOIN vectors v ON e.id=v.event_id AND v.model=?
            WHERE e.project_id=? AND (? IS NULL OR e.kind=?)
        """, (model, project_id, kind, kind)).fetchone()
        total = int(row["total"])
        indexed = int(row["indexed"])
        return {"indexed_records": indexed, "pending_records": total - indexed}

    def keyword_search(self, project_id: str, query: str, limit: int,
                       kind: str | None = None) -> list[dict]:
        tokens = [token for token in re.findall(r"[\w]+", query, flags=re.UNICODE)
                  if token.lower() not in SEARCH_STOPWORDS][:10]
        if not tokens:
            return []
        expression = " OR ".join(f'"{token}"' for token in tokens)
        rows = self.connection.execute("""
            SELECT e.* FROM event_fts f JOIN events e ON e.id=f.event_id
            WHERE e.project_id=? AND (? IS NULL OR e.kind=?) AND event_fts MATCH ?
            ORDER BY bm25(event_fts) LIMIT ?
        """, (project_id, kind, kind, expression, limit))
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
