import shlex
import sqlite3
import sys

import pytest

from arc.git_evidence import snapshot
from arc.service import ArcService


def test_claim_is_not_verified_without_matching_evidence(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo, command)
        task = service.add_task(sample_repo, "Build login")
        task_id = task["id"]
        service.record_note(sample_repo, "claim", "Login is complete", task_id)
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "planned"

        (sample_repo / "app.py").write_text("print('login')\n")
        service.capture_git(sample_repo, task_id)
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "implementation_observed"

        result = service.run_test(sample_repo, task_id)
        assert result["details"]["passed"] is True
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "tests_passed"
        assert service.confirm_task(sample_repo, task_id)["state"] == "completed_confirmed"

        (sample_repo / "app.py").write_text("print('changed again')\n")
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "implementation_observed"
        with pytest.raises(ValueError):
            service.confirm_task(sample_repo, task_id)
    finally:
        service.close()


def test_checkpoint_becomes_stale_after_project_change(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo)
        checkpoint = service.create_checkpoint(sample_repo)
        assert checkpoint["payload"]["status"] == "candidate_unconfirmed"
        assert service.project_state(sample_repo)["latest_checkpoint"]["stale"] is False
        (sample_repo / "another.py").write_text("x = 1\n")
        assert service.project_state(sample_repo)["latest_checkpoint"]["stale"] is True
    finally:
        service.close()


def test_git_capture_excludes_secret_paths(sample_repo, tmp_path):
    (sample_repo / ".env").write_text("SECRET=example\n")
    (sample_repo / "notes.md").write_text("hello\n")
    observed = snapshot(sample_repo)
    assert "notes.md" in observed.changed_paths
    assert ".env" not in observed.changed_paths


def test_event_reference_resolves_to_recorded_evidence(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo)
        event = service.record_note(sample_repo, "decision", "Keep the SQLite schema small")
        assert event["source_ref"] == f"arc:event/{event['id']}"
        assert service.get_event(sample_repo, event["id"])["summary"] == event["summary"]
    finally:
        service.close()


def test_events_follow_active_session_and_stop_after_end(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo, command)
        before = service.record_note(sample_repo, "note", "Before the session")
        assert before["session_id"] is None

        session = service.start_session(sample_repo, "Investigate login")
        assert service.project_state(sample_repo)["active_session"]["id"] == session["id"]
        with pytest.raises(ValueError, match="already active"):
            service.start_session(sample_repo, "Second session")

        note = service.record_note(sample_repo, "error", "Login request failed")
        (sample_repo / "app.py").write_text("print('login fixed')\n")
        change = service.capture_git(sample_repo)
        test = service.run_test(sample_repo)
        assert {note["session_id"], change["session_id"], test["session_id"]} == {session["id"]}
        history = service.session_history(sample_repo, session["id"])
        assert history["total_events"] == 3
        assert history["has_more"] is False
        assert [event["id"] for event in history["events"]] == [
            note["id"], change["id"], test["id"]
        ]
        assert service.project_state(sample_repo)["recent_events"][0]["session_id"] == session["id"]

        ended = service.end_session(sample_repo)
        assert ended["ended_at"] is not None
        assert service.active_session(sample_repo) is None
        after = service.record_note(sample_repo, "note", "After the session")
        assert after["session_id"] is None
        assert len(service.session_history(sample_repo, session["id"])["events"]) == 3
    finally:
        service.close()


def test_existing_events_migrate_without_session_assignment(tmp_path):
    database = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(database)
    connection.executescript("""
        CREATE TABLE projects (
            id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, name TEXT NOT NULL,
            test_command TEXT, created_at TEXT NOT NULL
        );
        CREATE TABLE events (
            id TEXT PRIMARY KEY, project_id TEXT NOT NULL REFERENCES projects(id),
            task_id TEXT, kind TEXT NOT NULL, summary TEXT NOT NULL,
            source TEXT NOT NULL, source_ref TEXT NOT NULL, git_head TEXT,
            fingerprint TEXT, details_json TEXT NOT NULL, created_at TEXT NOT NULL
        );
        INSERT INTO projects VALUES ('project1', '/tmp/legacy-project', 'legacy', NULL, '2026-01-01');
        INSERT INTO events VALUES (
            'event1', 'project1', NULL, 'note', 'Legacy evidence', 'explicit',
            'arc:event/event1', NULL, NULL, '{}', '2026-01-01'
        );
    """)
    connection.close()

    from arc.store import Store

    store = Store(database)
    try:
        assert store.get_event("event1")["session_id"] is None
        assert store.get_event("event1")["summary"] == "Legacy evidence"
        assert store.sessions("project1") == []
    finally:
        store.close()

