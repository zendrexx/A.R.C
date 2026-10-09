"""Small loopback dashboard over the same project-scoped service used by CLI and MCP."""

import json
import hashlib
import secrets
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from importlib.resources import files
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from arc.memory import EmbeddingUnavailable
from arc.service import ArcService

STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
}


def create_dashboard_server(db_path: Path, port: int = 8765) -> ThreadingHTTPServer:
    """Create a browser UI bound only to this computer's loopback interface."""
    token = secrets.token_urlsafe(32)
    database = db_path.expanduser().resolve()

    class Handler(BaseHTTPRequestHandler):
        def _headers(self, status: int, content_type: str, length: int) -> None:
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(length))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy",
                             "default-src 'self'; script-src 'self'; style-src 'self'; "
                             "connect-src 'self'; img-src 'self' data:; base-uri 'none'; "
                             "form-action 'self'")
            self.end_headers()

        def _respond(self, status: int, payload: dict | list) -> None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self._headers(status, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)

        def _allowed_host(self) -> bool:
            host = self.headers.get("Host", "").split(":", 1)[0].lower()
            return host in {"127.0.0.1", "localhost"}

        def _query(self) -> tuple[str, dict[str, str]]:
            parsed = urlsplit(self.path)
            query = {key: values[-1] for key, values in parse_qs(parsed.query).items()}
            return parsed.path, query

        @staticmethod
        def _project(query: dict[str, str]) -> Path:
            value = query.get("project", "")
            if not value:
                raise ValueError("Select a registered project")
            return Path(value)

        def _api_get(self, service: ArcService, route: str, query: dict[str, str]):
            if route == '/api/health':
                return {'service': 'arc-dashboard', 'database_id': hashlib.sha256(str(database).encode()).hexdigest()}
            if route == "/api/projects":
                return service.list_projects()
            if route == "/api/ai-status":
                return service.local_ai_status()
            project = self._project(query)
            if route == "/api/overview":
                return {"state": service.project_state(project),
                        "handoff": service.project_handoff(project)}
            if route == "/api/search":
                mode = query.get("mode", "semantic")
                if mode not in {"semantic", "keyword", "hybrid"}:
                    raise ValueError("Search mode must be semantic, keyword, or hybrid")
                return service.search_memory(
                    project, query.get("q", ""),
                    keyword_only=mode == "keyword", hybrid=mode == "hybrid",
                )
            if route == "/api/timeline":
                return service.project_timeline(
                    project, limit=30, offset=int(query.get("offset", "0")),
                    kind=query.get("kind") or None,
                )
            if route == "/api/task":
                return service.task_review(project, query.get("id", ""))
            if route == "/api/event":
                return service.get_event(project, query.get("id", ""))
            if route == "/api/checkpoints":
                return service.checkpoint_history(project)
            if route == "/api/incidents":
                return service.list_incidents(project)
            if route == "/api/incident":
                return service.incident_history(project, query.get("id", ""))
            if route == "/api/incident-search":
                return service.search_incidents(
                    project, query.get("q", ""), query.get("cause") or None,
                )
            raise ValueError("Unknown dashboard route")

        def do_GET(self) -> None:
            if not self._allowed_host():
                self._respond(403, {"error": "Use the local dashboard address"})
                return
            route, query = self._query()
            if route in STATIC_FILES:
                filename, content_type = STATIC_FILES[route]
                body = files("arc").joinpath("ui", filename).read_bytes()
                if route == "/":
                    body = body.replace(b"__ARC_REQUEST_TOKEN__", token.encode("ascii"))
                self._headers(200, content_type, len(body))
                self.wfile.write(body)
                return
            if not route.startswith("/api/"):
                self._respond(404, {"error": "Not found"})
                return
            service = ArcService(database)
            try:
                self._respond(200, self._api_get(service, route, query))
            except (ValueError, EmbeddingUnavailable) as error:
                self._respond(400, {"error": str(error)})
            finally:
                service.close()

        def do_POST(self) -> None:
            if not self._allowed_host() or self.headers.get("X-ARC-Token") != token:
                self._respond(403, {"error": "Dashboard request was not authorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._respond(400, {"error": "Invalid request size"})
                return
            if length < 1 or length > 16384:
                self._respond(400, {"error": "Invalid request size"})
                return
            try:
                data = json.loads(self.rfile.read(length))
                if not isinstance(data, dict):
                    raise ValueError("Expected a JSON object")
            except (ValueError, UnicodeDecodeError) as error:
                self._respond(400, {"error": str(error)})
                return
            route, _ = self._query()
            service = ArcService(database)
            try:
                if route == "/api/projects":
                    if not isinstance(data.get("path"), str) or not data["path"].strip():
                        raise ValueError("Project folder path is required")
                    result = service.register_project(
                        Path(data["path"]), data.get("test_command") or None,
                    )
                else:
                    project = self._project(data)
                    if route == "/api/pause":
                        if not isinstance(data.get("paused"), bool):
                            raise ValueError("paused must be true or false")
                        result = service.set_recording_paused(project, data["paused"])
                    elif route == "/api/checkpoint":
                        result = service.create_checkpoint(project)
                    elif route == "/api/index":
                        result = service.index_memory(project)
                    elif route == "/api/task/add":
                        result = service.add_task(project, data.get("title", ""))
                    elif route == "/api/task/confirm":
                        result = service.confirm_task(project, data.get("id", ""))
                    elif route == "/api/delete":
                        result = service.clear_project_memory(
                            project, data.get("confirmation", ""),
                        )
                    else:
                        raise ValueError("Unknown dashboard route")
                self._respond(200, result)
            except (ValueError, EmbeddingUnavailable) as error:
                self._respond(400, {"error": str(error)})
            finally:
                service.close()

        def log_message(self, format: str, *args) -> None:
            # The UI may request several panels at once; keep terminal output quiet.
            pass

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def run_dashboard(db_path: Path, port: int = 8765, open_browser: bool = True,
                  initial_project: Path | None = None) -> None:
    server = create_dashboard_server(db_path, port)
    address = f"http://127.0.0.1:{server.server_port}/"
    if initial_project:
        address += "?" + urlencode({"project": str(initial_project)})
    print(f"A.R.C. dashboard: {address}", flush=True)
    if open_browser:
        webbrowser.open(address)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
