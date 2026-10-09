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
        self.connection.execute("PRAGMA busy_timeout = 5000")
        self.connection.execute("PRAGMA journal_mode = WAL")
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
            CREATE TABLE IF NOT EXISTS project_controls (
                project_id TEXT PRIMARY KEY REFERENCES projects(id),
                recording_paused INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS observation_state (
                project_id TEXT PRIMARY KEY REFERENCES projects(id),
                enabled INTEGER NOT NULL DEFAULT 0,
                cursor_head TEXT,
                cursor_branch TEXT,
                worker_pid INTEGER,
                heartbeat_at TEXT,
                session_id TEXT REFERENCES sessions(id),
                updated_at TEXT NOT NULL
            );
            CREATE VIRTUAL TABLE IF NOT EXISTS event_fts USING fts5(event_id UNINDEXED, summary);
            CREATE TABLE IF NOT EXISTS observer_state (
                project_id TEXT PRIMARY KEY REFERENCES projects(id),
                enabled INTEGER NOT NULL DEFAULT 0, paused INTEGER NOT NULL DEFAULT 0,
                fingerprint TEXT, head TEXT, updated_at TEXT
            );
        """)
        columns = {row["name"] for row in self.connection.execute("PRAGMA table_info(events)")}
        if "session_id" not in columns:
            self.connection.execute(
                "ALTER TABLE events ADD COLUMN session_id TEXT REFERENCES sessions(id)"
            )
        if "dedup_key" not in columns:
            self.connection.execute("ALTER TABLE events ADD COLUMN dedup_key TEXT")
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
        self.connection.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS events_observation_dedup "
            "ON events(project_id, dedup_key) WHERE dedup_key IS NOT NULL"
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

    def projects(self) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM projects ORDER BY name COLLATE NOCASE, path"
        )
        return [dict(row) for row in rows]

    def recording_paused(self, project_id: str) -> bool:
        row = self.connection.execute(
            "SELECT recording_paused FROM project_controls WHERE project_id=?",
            (project_id,),
        ).fetchone()
        return bool(row[0]) if row else False

    def set_recording_paused(self, project_id: str, paused: bool) -> dict:
        updated_at = utc_now()
        self.connection.execute(
            """INSERT INTO project_controls VALUES (?, ?, ?)
               ON CONFLICT(project_id) DO UPDATE SET
               recording_paused=excluded.recording_paused, updated_at=excluded.updated_at""",
            (project_id, int(paused), updated_at),
        )
        self.connection.commit()
        return {"recording_paused": paused, "updated_at": updated_at}

    def observation_state(self, project_id: str) -> dict:
        row = self.connection.execute(
            "SELECT * FROM observation_state WHERE project_id=?", (project_id,)
        ).fetchone()
        return dict(row) if row else {
            "project_id": project_id, "enabled": 0, "cursor_head": None,
            "cursor_branch": None, "worker_pid": None, "heartbeat_at": None,
            "session_id": None, "updated_at": None,
        }

    def set_observation_enabled(self, project_id: str, enabled: bool,
                                head: str | None = None,
                                branch: str | None = None) -> dict:
        now = utc_now()
        with self.connection:
            self.connection.execute(
                """INSERT INTO observation_state
                   (project_id, enabled, cursor_head, cursor_branch, updated_at)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(project_id) DO UPDATE SET
                   enabled=excluded.enabled,
                   cursor_head=COALESCE(excluded.cursor_head, observation_state.cursor_head),
                   cursor_branch=COALESCE(excluded.cursor_branch, observation_state.cursor_branch),
                   updated_at=excluded.updated_at""",
                (project_id, int(enabled), head, branch, now),
            )
            if not enabled:
                self.connection.execute(
                    "UPDATE observation_state SET worker_pid=NULL, heartbeat_at=NULL "
                    "WHERE project_id=?", (project_id,)
                )
        return self.observation_state(project_id)

    def set_observation_cursor(self, project_id: str, head: str,
                               branch: str) -> None:
        self.connection.execute(
            """UPDATE observation_state SET cursor_head=?, cursor_branch=?,
               updated_at=? WHERE project_id=?""",
            (head, branch, utc_now(), project_id),
        )
        self.connection.commit()

    def set_observation_worker(self, project_id: str, pid: int | None,
                               session_id: str | None = None) -> None:
        self.connection.execute(
            """UPDATE observation_state SET worker_pid=?, heartbeat_at=?,
               session_id=?, updated_at=? WHERE project_id=?""",
            (pid, utc_now() if pid is not None else None,
             session_id, utc_now(), project_id),
        )
        self.connection.commit()

    def heartbeat_observation(self, project_id: str, pid: int) -> None:
        self.connection.execute(
            """UPDATE observation_state SET heartbeat_at=?, updated_at=?
               WHERE project_id=? AND worker_pid=?""",
            (utc_now(), utc_now(), project_id, pid),
        )
        self.connection.commit()

    def start_observation_session(self, project_id: str) -> dict:
        session_id = uuid4().hex[:12]
        now = utc_now()
        # An observation run never occupies the active-session slot; ended_at is
        # updated again when the worker stops so the row records its timespan.
        self.connection.execute(
            "INSERT INTO sessions VALUES (?, ?, ?, ?, ?)",
            (session_id, project_id, "Automatic observation", now, now),
        )
        self.connection.commit()
        return self.get_session(session_id)

    def finish_observation_session(self, session_id: str) -> None:
        self.connection.execute(
            "UPDATE sessions SET ended_at=? WHERE id=?", (utc_now(), session_id),
        )
        self.connection.commit()

    def watcher_event_count(self, project_id: str) -> int:
        row = self.connection.execute(
            "SELECT COUNT(*) FROM events WHERE project_id=? AND source='watcher'",
            (project_id,),
        ).fetchone()
        return int(row[0])

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
                  set_task_confirmed: bool | None = None,
                  dedup_key: str | None = None,
                  commit: bool = True, created_at: str | None = None) -> dict:
        if set_task_confirmed is not None and not task_id:
            raise ValueError("A task status change must name a task")
        if dedup_key and set_task_confirmed is not None:
            raise ValueError("An observation cannot confirm a task")
        if dedup_key:
            existing = self.connection.execute(
                "SELECT id FROM events WHERE project_id=? AND dedup_key=?",
                (project_id, dedup_key),
            ).fetchone()
            if existing:
                return self.get_event(existing["id"])

        event_id = uuid4().hex
        if source_ref == "auto":
            source_ref = f"arc:event/{event_id}"
        active = self.active_session(project_id)
        if commit:
            with self.connection:
                if set_task_confirmed is not None:
                    self.connection.execute(
                        "UPDATE tasks SET confirmed=? WHERE id=? AND project_id=?",
                        (int(set_task_confirmed), task_id, project_id),
                    )
                self.connection.execute(
                    """INSERT INTO events
                       (id, project_id, task_id, kind, summary, source, source_ref,
                        git_head, fingerprint, details_json, created_at, session_id, dedup_key)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (event_id, project_id, task_id, kind, summary, source, source_ref,
                     git_head, fingerprint, json.dumps(details or {}), created_at or utc_now(),
                     active["id"] if active else None, dedup_key),
                )
                self.connection.execute("INSERT INTO event_fts (event_id, summary) VALUES (?, ?)",
                                        (event_id, summary))
        else:
            if set_task_confirmed is not None:
                self.connection.execute(
                    "UPDATE tasks SET confirmed=? WHERE id=? AND project_id=?",
                    (int(set_task_confirmed), task_id, project_id),
                )
            self.connection.execute(
                """INSERT INTO events
                   (id, project_id, task_id, kind, summary, source, source_ref,
                    git_head, fingerprint, details_json, created_at, session_id, dedup_key)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (event_id, project_id, task_id, kind, summary, source, source_ref,
                 git_head, fingerprint, json.dumps(details or {}), created_at or utc_now(),
                 active["id"] if active else None, dedup_key),
            )
            self.connection.execute("INSERT INTO event_fts (event_id, summary) VALUES (?, ?)",
                                    (event_id, summary))
            # caller controls commit when commit=False

        return self.get_event(event_id)

    def timeline(self, project_id: str, limit: int = 20, offset: int = 0,
                 kind: str | None = None, since: str | None = None,
                 until: str | None = None, snapshot_rowid: int | None = None) -> dict:
        def utc(value):
            if not value:
                return None
            parsed = datetime.fromisoformat(value)
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat(timespec='seconds')
        since, until = utc(since), utc(until)
        if since and until and since >= until:
            raise ValueError('Timeline start must precede its exclusive end')
        limit, offset = min(max(limit, 1), 100), max(offset, 0)
        if snapshot_rowid is None:
            snapshot_rowid = self.connection.execute('SELECT COALESCE(MAX(rowid),0) FROM events WHERE project_id=?', (project_id,)).fetchone()[0]
        snapshot_rowid = max(0, snapshot_rowid)
        clauses = 'project_id=? AND rowid<=? AND (? IS NULL OR kind=?) AND (? IS NULL OR created_at>=?) AND (? IS NULL OR created_at<?)'
        args = (project_id, snapshot_rowid, kind, kind, since, since, until, until)
        total = self.connection.execute('SELECT COUNT(*) FROM events WHERE ' + clauses, args).fetchone()[0]
        rows = self.connection.execute('SELECT * FROM events WHERE ' + clauses +
            ' ORDER BY created_at DESC, rowid DESC LIMIT ? OFFSET ?', (*args, limit, offset))
        events = [self._event(row) for row in rows]
        return {'events': events, 'total_events': total, 'snapshot_rowid': snapshot_rowid,
                'next_offset': offset + len(events) if offset + len(events) < total else None}

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

    def timeline(self, project_id: str, limit: int, offset: int = 0,
                 kind: str | None = None) -> tuple[list[dict], int]:
        filter_sql = "project_id=? AND (? IS NULL OR kind=?)"
        arguments = (project_id, kind, kind)
        total = int(self.connection.execute(
            f"SELECT COUNT(*) FROM events WHERE {filter_sql}", arguments
        ).fetchone()[0])
        rows = self.connection.execute(
            f"SELECT * FROM events WHERE {filter_sql} ORDER BY rowid DESC LIMIT ? OFFSET ?",
            (*arguments, limit, offset),
        )
        return [self._event(row) for row in rows], total

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

    def pending_embeddings(self, project_id: str, model: str, limit: int = 100) -> list[dict]:
        rows = self.connection.execute("""
            SELECT e.* FROM events e LEFT JOIN vectors v
            ON e.id=v.event_id AND v.model=?
            WHERE e.project_id=? AND v.event_id IS NULL
            ORDER BY e.rowid DESC LIMIT ?""", (model, project_id, limit))
        return [self._event(row) for row in rows]

        rows = self.connection.execute("""
            SELECT e.* FROM events e LEFT JOIN vectors v
            ON e.id=v.event_id AND v.model=?
            WHERE e.project_id=? AND v.event_id IS NULL ORDER BY e.rowid LIMIT ?
        """, (model, project_id, max(1, min(limit, 100))))
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

    def checkpoints(self, project_id: str, limit: int = 20) -> list[dict]:
        rows = self.connection.execute(
            "SELECT * FROM checkpoints WHERE project_id=? ORDER BY rowid DESC LIMIT ?",
            (project_id, limit),
        )
        result = []
        for row in rows:
            item = dict(row)
            item["payload"] = json.loads(item.pop("payload_json"))
            result.append(item)
        return result

    def clear_project_memory(self, project_id: str) -> dict:
        events = self.project_event_count(project_id)
        tasks = int(self.connection.execute(
            "SELECT COUNT(*) FROM tasks WHERE project_id=?", (project_id,)
        ).fetchone()[0])
        with self.connection:
            self.connection.execute(
                """DELETE FROM incident_links WHERE incident_id IN
                   (SELECT id FROM incidents WHERE project_id=?)""", (project_id,)
            )
            self.connection.execute("DELETE FROM incidents WHERE project_id=?", (project_id,))
            self.connection.execute(
                "DELETE FROM vectors WHERE event_id IN (SELECT id FROM events WHERE project_id=?)",
                (project_id,),
            )
            self.connection.execute(
                "DELETE FROM event_fts WHERE event_id IN (SELECT id FROM events WHERE project_id=?)",
                (project_id,),
            )
            self.connection.execute("DELETE FROM events WHERE project_id=?", (project_id,))
            self.connection.execute("DELETE FROM checkpoints WHERE project_id=?", (project_id,))
            self.connection.execute("DELETE FROM tasks WHERE project_id=?", (project_id,))
            self.connection.execute("DELETE FROM sessions WHERE project_id=?", (project_id,))
            self.connection.execute("DELETE FROM project_controls WHERE project_id=?", (project_id,))
            self.connection.execute("DELETE FROM observation_state WHERE project_id=?", (project_id,))
        return {"deleted_events": events, "deleted_tasks": tasks,
                "project_registration_kept": True}
