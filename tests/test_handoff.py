import shlex
import sys

import pytest

from arc.service import ArcService


def test_handoff_selects_recorded_context_and_keeps_claims_unverified(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo)
        empty = service.project_handoff(sample_repo)
        assert empty["status"] == "no_recorded_events"
        assert empty["suggested_next_task"] is None
        assert empty["key_evidence"] == []

        task_id = service.add_task(sample_repo, "Repair login")["id"]
        session_id = service.start_session(sample_repo, "Investigate login")["id"]
        decision = service.record_note(sample_repo, "decision", "Keep sessions in SQLite", task_id)
        failure = service.record_note(sample_repo, "error", "Login request timed out", task_id)
        attempt = service.record_note(sample_repo, "attempt", "Tried a longer timeout", task_id)
        claim = service.record_note(sample_repo, "claim", "Login is fixed", task_id)
        for _ in range(3):
            service.record_note(sample_repo, "note", "Repeated low-priority observation")
        handoff = service.project_handoff(sample_repo)

        assert handoff["project"]["path"] == str(sample_repo)
        assert handoff["git"]["fingerprint"]
        assert handoff["active_session"]["id"] == session_id
        assert handoff["latest_session"]["id"] == session_id
        assert handoff["total_unfinished_tasks"] == 1
        assert handoff["suggested_next_task"]["id"] == task_id
        assert handoff["suggested_next_task"]["state"] == "planned"
        assert handoff["unfinished_tasks"][0]["unverified_agent_claim"] == "Login is fixed"
        assert {item["category"] for item in handoff["key_evidence"]} >= {
            "decision", "failure", "attempt"
        }
        selected_ids = {item["id"] for item in handoff["key_evidence"]}
        assert {decision["id"], failure["id"], attempt["id"]} <= selected_ids
        assert claim["id"] not in selected_ids
        assert all(service.get_event(sample_repo, item["id"])["source_ref"] == item["source_ref"]
                   for item in handoff["key_evidence"])
        assert all(item["session_id"] == session_id for item in handoff["key_evidence"]
                   if item["task_id"] == task_id)
        assert handoff["history_window"]["total_events"] == 7
        assert handoff["history_window"]["truncated"] is False
        assert len(handoff["key_evidence"]) <= 6
        assert [item["rank"] for item in handoff["key_evidence"]] == list(
            range(1, len(handoff["key_evidence"]) + 1)
        )
        with pytest.raises(ValueError, match="between 1 and 12"):
            service.project_handoff(sample_repo, 0)
        service.end_session(sample_repo)
        after_session = service.project_handoff(sample_repo)
        assert after_session["active_session"] is None
        assert after_session["latest_session"]["id"] == session_id
        assert after_session["latest_session"]["ended_at"] is not None
    finally:
        service.close()


def test_handoff_excludes_superseded_and_stale_verification(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3")
    try:
        service.register_project(sample_repo, command)
        task_id = service.add_task(sample_repo, "Repair login")["id"]
        (sample_repo / "app.py").write_text("print('login')\n")
        service.capture_git(sample_repo, task_id)
        old_test = service.run_test(sample_repo, task_id)
        service.confirm_task(sample_repo, task_id)
        confirmed = service.project_handoff(sample_repo)
        assert confirmed["total_confirmed_tasks"] == 1
        assert confirmed["total_unfinished_tasks"] == 0
        assert confirmed["suggested_next_task"] is None
        assert len(confirmed["confirmed_tasks"][0]["current_confirmation_refs"]) == 1

        service.correct_task(sample_repo, task_id, "implementation_observed",
                             "The earlier test missed a case")
        corrected = service.project_handoff(sample_repo)
        assert corrected["total_unfinished_tasks"] == 1
        assert corrected["suggested_next_task"]["state"] == "implementation_observed"
        assert corrected["unfinished_tasks"][0]["current_passing_test_refs"] == []
        assert corrected["unfinished_tasks"][0]["current_confirmation_refs"] == []
        assert old_test["id"] not in {item["id"] for item in corrected["key_evidence"]}
        assert not any(item["kind"] == "confirmation" for item in corrected["key_evidence"])

        new_test = service.run_test(sample_repo, task_id)
        tested = service.project_handoff(sample_repo)
        assert tested["suggested_next_task"]["state"] == "tests_passed"
        assert f"arc:event/{new_test['id']}" in tested["unfinished_tasks"][0][
            "current_passing_test_refs"
        ]
        service.confirm_task(sample_repo, task_id)
        (sample_repo / "app.py").write_text("print('changed login')\n")
        stale = service.project_handoff(sample_repo)
        assert stale["total_confirmed_tasks"] == 0
        assert stale["suggested_next_task"]["state"] == "implementation_observed"
        assert new_test["id"] not in {item["id"] for item in stale["key_evidence"]}
    finally:
        service.close()
