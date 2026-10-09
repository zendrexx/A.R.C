import shlex
import subprocess
import sys

import pytest

from arc.memory import EmbeddingUnavailable
from arc.service import ArcService


class IncidentEmbedder:
    model = "incident-fixture"

    def embed(self, text: str) -> list[float]:
        lowered = text.lower()
        if "locked" in lowered:
            return [0.7, 0.7, 0.0]
        if "migration" in lowered or "upgrade" in lowered:
            return [1.0, 0.0, 0.0]
        return [0.0, 0.0, 1.0]


class OfflineEmbedder:
    model = "offline"

    def embed(self, text: str) -> list[float]:
        raise EmbeddingUnavailable("Ollama is not running")


def test_incident_history_links_attempts_resolution_and_current_test(sample_repo, tmp_path):
    command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
    service = ArcService(tmp_path / "arc.sqlite3", IncidentEmbedder())
    try:
        service.register_project(sample_repo, command)
        error = service.record_note(sample_repo, "error", "SQLite migration failed: users table missing")
        incident = service.open_incident(sample_repo, error["id"], "users table absent")
        incident_id = incident["id"]
        assert incident["status"] == "open"
        assert incident["error"]["source_ref"] == error["source_ref"]
        assert incident["cause_source_ref"].startswith("arc:event/")
        cause_id = incident["cause_source_ref"].split("/")[-1]
        assert "users table absent" in service.get_event(sample_repo, cause_id)["summary"]
        with pytest.raises(ValueError, match="already has an incident"):
            service.open_incident(sample_repo, error["id"])

        failed = service.add_incident_attempt(
            sample_repo, incident_id, "Retried migration without the schema", "failed"
        )
        assert failed["timeline"][1]["outcome"] == "failed"
        old_attempt = service.record_note(sample_repo, "attempt", "Checked migration order")
        linked = service.link_incident_attempt(
            sample_repo, incident_id, old_attempt["id"], "helped"
        )
        assert linked["timeline"][2]["source_ref"] == old_attempt["source_ref"]
        assert linked["timeline"][2]["outcome"] == "helped"
        (sample_repo / "app.py").write_text("print('schema fixed')\n")
        test = service.run_test(sample_repo)
        resolved = service.resolve_incident(
            sample_repo, incident_id, "Added users table before migration",
            test_event_id=test["id"],
        )
        assert resolved["status"] == "reported_resolved"
        assert resolved["resolution"]["role"] == "resolution"
        assert resolved["resolution"]["source_ref"].startswith("arc:event/")
        assert resolved["linked_tests"][0]["source_ref"] == test["source_ref"]
        assert resolved["linked_tests"][0]["current_passing"] is True
        assert "do not prove" in resolved["evidence_limit"]
        assert any(item["category"] == "resolution"
                   for item in service.project_handoff(sample_repo)["key_evidence"])
        assert service.list_incidents(sample_repo)[0]["id"] == incident_id
        with pytest.raises(ValueError, match="already has a reported resolution"):
            service.resolve_incident(sample_repo, incident_id, "Another fix")
        (sample_repo / "app.py").write_text("print('later change')\n")
        assert service.incident_history(sample_repo, incident_id)["linked_tests"][0][
            "current_passing"
        ] is False
    finally:
        service.close()


def test_incident_search_separates_different_causes_and_weak_results(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3", IncidentEmbedder())
    try:
        service.register_project(sample_repo)
        missing = service.record_note(sample_repo, "error", "SQLite migration failed: users table missing")
        locked = service.record_note(sample_repo, "error", "SQLite migration failed: database locked")
        first = service.open_incident(sample_repo, missing["id"], "users table absent")
        second = service.open_incident(sample_repo, locked["id"], "database file locked")
        service.add_incident_attempt(sample_repo, first["id"], "Created the users table", "helped")
        service.resolve_incident(sample_repo, first["id"], "Run schema creation before migration")
        service.index_memory(sample_repo)

        found = service.search_incidents(
            sample_repo, "Database upgrade crashed during migration", "users table absent"
        )
        assert found["mode"] == "semantic"
        assert [item["incident_id"] for item in found["candidates"]] == [first["id"]]
        assert [item["incident_id"] for item in found["different_causes"]] == [second["id"]]
        assert found["candidates"][0]["cause_relation"] == "same_recorded_cause"
        assert found["candidates"][0]["cause_source_ref"] == first["cause_source_ref"]
        assert found["candidates"][0]["match_status"] == "candidate_not_confirmed"
        assert found["candidates"][0]["timeline"][0]["source_ref"] == missing["source_ref"]
        assert found["different_causes"][0]["cause_relation"] == "different_recorded_cause"

        unknown_cause = service.search_incidents(sample_repo, "Database upgrade crashed")
        assert all(item["cause_relation"] == "cause_not_supplied"
                   for item in unknown_cause["candidates"])
        unrelated = service.search_incidents(sample_repo, "Recipe timer stopped on close")
        assert unrelated["candidates"] == []
        assert unrelated["different_causes"] == []
        assert unrelated["weak_rejections"] >= 1
    finally:
        service.close()


def test_incident_rejects_wrong_project_and_invalid_evidence(sample_repo, tmp_path):
    service = ArcService(tmp_path / "arc.sqlite3", OfflineEmbedder())
    try:
        command = f"{shlex.quote(sys.executable)} -c \"print('pass')\""
        service.register_project(sample_repo, command)
        prior_test = service.run_test(sample_repo)
        other = tmp_path / "other-project"
        other.mkdir()
        subprocess.run(["git", "init", "-q", str(other)], check=True)
        service.register_project(other)
        error = service.record_note(sample_repo, "error", "Database request failed")
        decision = service.record_note(sample_repo, "decision", "Keep SQLite")
        with pytest.raises(ValueError, match="recorded error"):
            service.open_incident(sample_repo, decision["id"])
        incident = service.open_incident(sample_repo, error["id"])
        with pytest.raises(ValueError, match="not found in this project"):
            service.incident_history(other, incident["id"])
        with pytest.raises(ValueError, match="not found in this project"):
            service.open_incident(other, error["id"])
        with pytest.raises(ValueError, match="Only an attempt event"):
            service.link_incident_attempt(sample_repo, incident["id"], decision["id"])
        with pytest.raises(ValueError, match="Linked test must have passed"):
            service.resolve_incident(sample_repo, incident["id"], "Looks fixed",
                                     test_event_id=decision["id"])
        with pytest.raises(ValueError, match="after the error"):
            service.resolve_incident(sample_repo, incident["id"], "Looks fixed",
                                     test_event_id=prior_test["id"])
        assert service.incident_history(sample_repo, incident["id"])["status"] == "open"
        fallback = service.search_incidents(sample_repo, "Database problem")
        assert fallback["mode"] == "keyword_fallback"
        assert fallback["candidates"] == []  # One shared specific token is insufficient.
        resolved = service.resolve_incident(
            sample_repo, incident["id"], "Reset the database connection", "stale pool entry"
        )
        assert resolved["cause"] == "stale pool entry"
        assert resolved["cause_source_ref"] == resolved["resolution"]["source_ref"]
    finally:
        service.close()
