"""Dashboard HTTP contract and project-scoped privacy controls."""

import json
import re
import subprocess
from contextlib import contextmanager
from pathlib import Path
from threading import Thread
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pytest

from arc.dashboard import create_dashboard_server
from arc.service import ArcService


@contextmanager
def dashboard(database: Path):
    server = create_dashboard_server(database, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def request(base: str, route: str, query: dict | None = None,
            data: dict | None = None, token: str | None = None):
    url = base + route + ("?" + urlencode(query) if query else "")
    headers = {}
    if data is not None:
        headers["Content-Type"] = "application/json"
        if token:
            headers["X-ARC-Token"] = token
    req = Request(url, headers=headers,
                  data=json.dumps(data).encode() if data is not None else None)
    try:
        with urlopen(req, timeout=10) as response:
            body = response.read()
            return response.status, (json.loads(body) if route.startswith("/api/")
                                     else body.decode())
    except HTTPError as error:
        return error.code, json.load(error)


def test_dashboard_project_views_and_authorized_controls(sample_repo, tmp_path):
    database = tmp_path / "arc.sqlite3"
    service = ArcService(database)
    try:
        service.register_project(sample_repo)
        task = service.add_task(sample_repo, "Implement handoff")
        event = service.record_note(sample_repo, "decision", "Use source-linked records")
        checkpoint = service.create_checkpoint(sample_repo)
    finally:
        service.close()

    with dashboard(database) as base:
        status, html = request(base, "/")
        assert status == 200
        token = re.search(r'<meta name="arc-token" content="([^"]+)">', html).group(1)
        assert "A.R.C." in html and token != "__ARC_REQUEST_TOKEN__"
        assert "function loadOverview" in request(base, "/app.js")[1]
        assert ".app-shell" in request(base, "/style.css")[1]

        query = {"project": str(sample_repo)}
        assert request(base, "/api/projects")[1][0]["path"] == str(sample_repo)
        overview = request(base, "/api/overview", query)[1]
        assert overview["handoff"]["suggested_next_task"]["id"] == task["id"]
        assert overview["state"]["tasks"][0]["state"] == "planned"
        assert request(base, "/api/task", {**query, "id": task["id"]})[1]["missing"]
        assert request(base, "/api/timeline", query)[1]["events"][0]["id"] == event["id"]
        assert request(base, "/api/timeline", {**query, "kind": "error"})[1]["total"] == 0
        assert request(base, "/api/search", {**query, "q": "source-linked", "mode": "keyword"})[1]["hits"][0]["event_id"] == event["id"]
        assert request(base, "/api/checkpoints", query)[1][0]["id"] == checkpoint["id"]
        assert request(base, "/api/event", {**query, "id": event["id"]})[1]["source_ref"] == event["source_ref"]

        assert request(base, "/api/pause", data={**query, "paused": True})[0] == 403
        assert request(base, "/api/pause", data={**query, "paused": True}, token=token)[1]["recording_paused"]
        reopened = ArcService(database)
        try:
            with pytest.raises(ValueError, match="paused"):
                reopened.record_note(sample_repo, "note", "Should not be saved")
        finally:
            reopened.close()
        assert request(base, "/api/pause", data={**query, "paused": False}, token=token)[1]["recording_paused"] is False
        assert request(base, "/api/task/add", data={**query, "title": "New work"}, token=token)[0] == 200


def test_dashboard_delete_requires_exact_confirmation_and_stays_in_project(sample_repo, tmp_path):
    database = tmp_path / "arc.sqlite3"
    other = tmp_path / "other-project"
    other.mkdir()
    subprocess.run(["git", "init", "-q", str(other)], check=True)
    service = ArcService(database)
    try:
        service.register_project(sample_repo)
        service.register_project(other)
        task = service.add_task(sample_repo, "Private task")
        service.start_session(sample_repo, "Private session")
        private = service.record_note(sample_repo, "note", "Private memory")
        error = service.record_note(sample_repo, "error", "Private error")
        service.open_incident(sample_repo, error["id"])
        service.store.put_vector(private["id"], "all-minilm", [1.0])
        service.end_session(sample_repo)
        service.record_note(other, "note", "Keep other project")
        service.create_checkpoint(sample_repo)
        service.set_recording_paused(sample_repo, True)
    finally:
        service.close()

    with dashboard(database) as base:
        token = re.search(r'<meta name="arc-token" content="([^"]+)">',
                          request(base, "/")[1]).group(1)
        data = {"project": str(sample_repo), "confirmation": "DELETE wrong"}
        assert request(base, "/api/delete", data=data, token=token)[0] == 400
        assert request(base, "/api/task", {"project": str(sample_repo), "id": task["id"]})[0] == 200
        data["confirmation"] = f"DELETE {sample_repo.name}"
        deleted = request(base, "/api/delete", data=data, token=token)[1]
        assert deleted["deleted_events"] == 2 and deleted["deleted_tasks"] == 1
        empty = request(base, "/api/overview", {"project": str(sample_repo)})[1]
        assert empty["state"]["tasks"] == []
        assert empty["state"]["recording"]["recording_paused"] is False
        assert request(base, "/api/checkpoints", {"project": str(sample_repo)})[1] == []
        assert request(base, "/api/incidents", {"project": str(sample_repo)})[1] == []
        assert request(base, "/api/search", {"project": str(sample_repo), "q": "Private", "mode": "keyword"})[1]["hits"] == []
        assert empty["state"]["memory_index"]["indexed_records"] == 0
        assert request(base, "/api/timeline", {"project": str(other)})[1]["total"] == 1
        assert len(request(base, "/api/projects")[1]) == 2
    reopened = ArcService(database)
    try:
        assert reopened.sessions(sample_repo) == []
    finally:
        reopened.close()
