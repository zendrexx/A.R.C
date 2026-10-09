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


def test_correction_downgrades_status_and_keeps_an_audit_trail(sample_repo, tmp_path):
    database = tmp_path / "arc.sqlite3"
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(database)
    try:
        service.register_project(sample_repo, command)
        task_id = service.add_task(sample_repo, "Build login")["id"]
        session_id = service.start_session(sample_repo, "Review login")["id"]
        (sample_repo / "app.py").write_text("print('login')\n")
        change = service.capture_git(sample_repo, task_id)
        old_test = service.run_test(sample_repo, task_id)
        assert service.confirm_task(sample_repo, task_id)["state"] == "completed_confirmed"

        corrected = service.correct_task(
            sample_repo, task_id, "implementation_observed", "The earlier test missed a case"
        )
        assert corrected["state"] == "implementation_observed"
        assert corrected["confirmed_by_user"] is False
        assert corrected["implementation_event_ids"] == [change["id"]]
        assert corrected["current_passing_test_event_ids"] == []
        correction = service.get_event(sample_repo, corrected["latest_correction"]["id"])
        assert correction["session_id"] == session_id
        assert correction["source_ref"] == f"arc:event/{correction['id']}"
        assert correction["details"]["reason"] == "The earlier test missed a case"

        review = service.task_review(sample_repo, task_id)
        assert review["requirements"]["observed_change"] is True
        assert review["requirements"]["current_passing_test"] is False
        assert f"arc test --task {task_id}" in review["missing"][0]
        prior_test = next(item for item in review["recent_evidence"] if item["id"] == old_test["id"])
        assert prior_test["counts_for_current_state"] is False
        assert prior_test["evidence_status"] == "superseded_by_correction"
        assert prior_test["source_ref"] == old_test["source_ref"]
        with pytest.raises(ValueError, match="current passing test"):
            service.confirm_task(sample_repo, task_id)

        service.run_test(sample_repo, task_id)
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "tests_passed"
        assert service.confirm_task(sample_repo, task_id)["state"] == "completed_confirmed"

        planned = service.correct_task(sample_repo, task_id, "planned", "Work needs a redesign")
        assert planned["state"] == "planned"
        service.capture_git(sample_repo, task_id)
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "planned"
        (sample_repo / "app.py").write_text("print('redesigned login')\n")
        service.capture_git(sample_repo, task_id)
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "implementation_observed"
    finally:
        service.close()

    reopened = ArcService(database)
    try:
        state = reopened.project_state(sample_repo)["tasks"][0]
        assert state["state"] == "implementation_observed"
        assert state["latest_correction"]["to_state"] == "planned"
    finally:
        reopened.close()


def test_correction_cannot_invent_evidence_or_confirmation(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo, command)
        task_id = service.add_task(sample_repo, "Build login")["id"]
        with pytest.raises(ValueError, match="only set planned"):
            service.correct_task(sample_repo, task_id, "tests_passed", "Looks ready")
        with pytest.raises(ValueError, match="linked Git change"):
            service.correct_task(sample_repo, task_id, "implementation_observed", "Looks done")
        with pytest.raises(ValueError, match="needs a reason"):
            service.correct_task(sample_repo, task_id, "planned", " ")
        assert service.project_state(sample_repo)["tasks"][0]["state"] == "planned"
    finally:
        service.close()


def test_new_test_does_not_reuse_confirmation_from_older_git_state(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo, command)
        task_id = service.add_task(sample_repo, "Build login")["id"]
        (sample_repo / "app.py").write_text("print('login')\n")
        service.capture_git(sample_repo, task_id)
        service.run_test(sample_repo, task_id)
        assert service.confirm_task(sample_repo, task_id)["state"] == "completed_confirmed"
        (sample_repo / "app.py").write_text("print('changed login')\n")
        service.run_test(sample_repo, task_id)
        updated = service.project_state(sample_repo)["tasks"][0]
        assert updated["state"] == "tests_passed"
        assert updated["confirmed_by_user"] is False
        assert service.confirm_task(sample_repo, task_id)["state"] == "completed_confirmed"
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

