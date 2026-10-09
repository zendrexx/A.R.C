import shlex
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

