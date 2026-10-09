import os
import shlex
import subprocess
import sys

import pytest

from arc.observe import Observer
from arc.service import ArcService


def _commit_all(repo, message):
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "commit", "-qm", message], check=True)


def _watcher_events(service, project_id, kind=None):
    events = [event for event in service.store.events(project_id, 200)
              if event["source"] == "watcher"]
    if kind:
        events = [event for event in events if event["kind"] == kind]
    return events


def _observed(service, repo, test_command=None):
    service.register_project(repo, test_command)
    project = service.start_observation(repo)["project"]
    observer = Observer(service.store, project, settle_seconds=0, git_seconds=0)
    observer.start()
    return project["id"], observer


def test_repeated_saves_record_one_event_and_a_real_change_records_once(
        sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        (sample_repo / "app.py").write_text("print('version 2')\n")
        observer.tick()
        assert len(_watcher_events(service, project_id, "file_change")) == 1

        for _ in range(10):
            os.utime(sample_repo / "app.py")
            observer.tick()
        events = _watcher_events(service, project_id, "file_change")
        assert len(events) == 1
        assert events[0]["summary"] == "File modified: app.py"
        assert events[0]["details"]["path"] == "app.py"
        assert events[0]["source_ref"] == f"arc:event/{events[0]['id']}"

        (sample_repo / "app.py").write_text("print('version 3')\n")
        observer.tick()
        assert len(_watcher_events(service, project_id, "file_change")) == 2
        observer.tick()
        assert len(_watcher_events(service, project_id, "file_change")) == 2
        observer.stop()
    finally:
        service.close()


def test_new_file_and_deletion_are_observed(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        (sample_repo / "extra.py").write_text("x = 1\n")
        observer.tick()
        (sample_repo / "extra.py").unlink()
        observer.tick()
        summaries = [event["summary"]
                     for event in _watcher_events(service, project_id, "file_change")]
        assert "File created: extra.py" in summaries
        assert "File deleted: extra.py" in summaries
        observer.stop()
    finally:
        service.close()


def test_commit_cursor_recovers_commits_made_while_worker_was_down(
        sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        observer.stop()

        (sample_repo / "feature.py").write_text("def feature():\n    return 1\n")
        _commit_all(sample_repo, "add feature module")

        restarted = Observer(service.store, {"id": project_id,
                                             "path": str(sample_repo)},
                             settle_seconds=0, git_seconds=0)
        restarted.start()
        commits = _watcher_events(service, project_id, "commit")
        assert len(commits) == 1
        assert "add feature module" in commits[0]["summary"]
        assert commits[0]["details"]["commit"]

        restarted.check_git()
        assert len(_watcher_events(service, project_id, "commit")) == 1
        restarted.stop()

        again = Observer(service.store, {"id": project_id,
                                         "path": str(sample_repo)},
                         settle_seconds=0, git_seconds=0)
        again.start()
        assert len(_watcher_events(service, project_id, "commit")) == 1
        again.stop()
    finally:
        service.close()


def test_sensitive_files_produce_no_stored_event_text(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        (sample_repo / ".env").write_text("TOKEN=supersecretvalue123\n")
        (sample_repo / "keys.pem").write_text("private key material\n")
        (sample_repo / "visible.py").write_text("x = 2\n")
        observer.tick()
        watcher = _watcher_events(service, project_id, "file_change")
        paths = [event["details"].get("path") for event in watcher]
        assert paths == ["visible.py"]
        assert all("supersecretvalue" not in event["summary"]
                   and "private key material" not in event["summary"]
                   for event in watcher)
        observer.stop()
    finally:
        service.close()


def test_pause_stops_collection_and_resume_establishes_a_new_baseline(
        sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        service.set_recording_paused(sample_repo, True)

        (sample_repo / "paused.py").write_text("x = 3\n")
        _commit_all(sample_repo, "committed while paused")
        assert observer.tick() is True
        assert _watcher_events(service, project_id, "file_change") == []
        assert _watcher_events(service, project_id, "commit") == []

        service.set_recording_paused(sample_repo, False)
        assert observer.tick() is True
        assert observer.tick() is True
        assert _watcher_events(service, project_id, "file_change") == []
        assert _watcher_events(service, project_id, "commit") == []

        (sample_repo / "paused.py").write_text("x = 4\n")
        observer.tick()
        events = _watcher_events(service, project_id, "file_change")
        assert [event["details"]["path"] for event in events] == ["paused.py"]
        observer.stop()
    finally:
        service.close()


def test_observed_file_events_never_verify_or_confirm_a_task(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo, test_command=command)
        task_id = service.add_task(sample_repo, "Build feature")["id"]
        (sample_repo / "app.py").write_text("print('implemented')\n")
        observer.tick()
        assert _watcher_events(service, project_id, "file_change")
        state = service.project_state(sample_repo)["tasks"][0]
        assert state["state"] == "planned"
        with pytest.raises(ValueError, match="current passing test"):
            service.confirm_task(sample_repo, task_id)
        observer.stop()
    finally:
        service.close()


def test_status_reports_worker_and_disable_stops_it(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        project_id, observer = _observed(service, sample_repo)
        status = service.observation_status(sample_repo)
        assert status["enabled"] is True
        assert status["worker_pid"] == os.getpid()
        assert status["worker_process_alive"] is True
        assert status["cursor_head"]
        session_id = status["session_id"]
        assert session_id

        assert service.stop_observation(sample_repo)["enabled"] is False
        assert observer.tick() is False
        observer.stop()
        status = service.observation_status(sample_repo)
        assert status["worker_pid"] is None
        assert status["session_id"] is None

        session = service.store.get_session(session_id)
        assert session["label"] == "Automatic observation"
        assert session["ended_at"]
        observer.start()
        assert service.observation_status(sample_repo)["enabled"] is False
        observer.tick()
        observer.stop()
    finally:
        service.close()
