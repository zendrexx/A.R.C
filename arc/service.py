"""Evidence rules and the stable service boundary used by CLI and MCP."""

import shlex
import subprocess
from pathlib import Path

from arc.git_evidence import snapshot
from arc.memory import Embedder, MemoryEngine, redact
from arc.store import Store

NOTE_KINDS = {"note", "decision", "attempt", "error", "claim"}


class ArcService:
    def __init__(self, db_path: Path, embedder: Embedder | None = None):
        self.store = Store(db_path)
        self.memory = MemoryEngine(self.store, embedder)

    def close(self) -> None:
        self.store.close()

    def register_project(self, path: Path, test_command: str | None = None) -> dict:
        observed = snapshot(path)
        if test_command is not None and not shlex.split(test_command):
            raise ValueError("Test command must name an executable")
        return self.store.register_project(observed.root, test_command)

    def _project(self, path: Path) -> dict:
        project = self.store.get_project(path)
        if not project:
            raise ValueError(f"Project is not registered: {path.resolve()}. Run 'arc init' first.")
        return project

    def _task(self, project_id: str, task_id: str) -> dict:
        task = self.store.get_task(task_id)
        if not task or task["project_id"] != project_id:
            raise ValueError("Task was not found in this project")
        return task

    def add_task(self, path: Path, title: str) -> dict:
        if not title.strip():
            raise ValueError("Task title must not be empty")
        project = self._project(path)
        return self.store.add_task(project["id"], redact(title.strip()))

    def start_session(self, path: Path, label: str = "Development session") -> dict:
        if not label.strip():
            raise ValueError("Session label must not be empty")
        project = self._project(path)
        return self.store.start_session(project["id"], redact(label.strip()))

    def end_session(self, path: Path) -> dict:
        return self.store.end_session(self._project(path)["id"])

    def active_session(self, path: Path) -> dict | None:
        return self.store.active_session(self._project(path)["id"])

    def sessions(self, path: Path, limit: int = 20) -> list[dict]:
        return self.store.sessions(self._project(path)["id"], min(max(limit, 1), 100))

    def session_history(self, path: Path, session_id: str) -> dict:
        project = self._project(path)
        session = self.store.get_session(session_id)
        if not session or session["project_id"] != project["id"]:
            raise ValueError("Session was not found in this project")
        events = self.store.session_events(project["id"], session_id)
        total = self.store.session_event_count(project["id"], session_id)
        return {"session": session, "events": events,
                "total_events": total, "has_more": total > len(events)}

    def record_note(self, path: Path, kind: str, text: str,
                    task_id: str | None = None) -> dict:
        if kind not in NOTE_KINDS:
            raise ValueError(f"Unsupported note kind: {kind}")
        if not text.strip():
            raise ValueError("Note text must not be empty")
        project = self._project(path)
        if task_id:
            self._task(project["id"], task_id)
        if kind == "claim" and not task_id:
            raise ValueError("A progress claim must name a task")
        summary = redact(text.strip())
        observed = snapshot(Path(project["path"]))
        event = self.store.add_event(
            project["id"], kind, summary, "explicit", "auto", task_id,
            observed.head, observed.fingerprint,
        )
        if kind == "claim":
            self.store.set_claim(task_id, summary)
        return event

    def capture_git(self, path: Path, task_id: str | None = None) -> dict:
        project = self._project(path)
        if task_id:
            self._task(project["id"], task_id)
        observed = snapshot(Path(project["path"]))
        changed = list(observed.changed_paths)
        summary = ("Git changes: " + ", ".join(changed[:30])) if changed else "Git working tree clean"
        if len(changed) > 30:
            summary += f" (+{len(changed) - 30} more)"
        return self.store.add_event(
            project["id"], "git", summary, "git", "auto",
            task_id, observed.head, observed.fingerprint,
            {"changed_paths": changed, "has_visible_changes": bool(changed)},
        )

    def run_test(self, path: Path, task_id: str | None = None,
                 timeout_seconds: int = 120) -> dict:
        project = self._project(path)
        if task_id:
            self._task(project["id"], task_id)
        command = project["test_command"]
        if not command:
            raise ValueError("No test command configured. Re-run 'arc init --test-command ...'.")
        argv = shlex.split(command)
        before = snapshot(Path(project["path"]))
        try:
            completed = subprocess.run(
                argv, cwd=project["path"], capture_output=True, text=True,
                timeout=timeout_seconds, check=False, errors="replace",
            )
            exit_code = completed.returncode
            output = (completed.stdout + "\n" + completed.stderr)[-4000:]
        except (subprocess.TimeoutExpired, OSError) as error:
            exit_code = -1
            output = str(error)
        after = snapshot(Path(project["path"]))
        stable = before.fingerprint == after.fingerprint
        passed = exit_code == 0 and stable
        summary = f"Test {'passed' if passed else 'failed'}: {command}"
        if not stable:
            summary += " (project changed during test)"
        return self.store.add_event(
            project["id"], "test", summary, "configured_test", "auto",
            task_id, before.head, before.fingerprint,
            {"command": command, "exit_code": exit_code, "passed": passed,
             "snapshot_stable": stable, "output_tail": redact(output)},
        )

    def _task_state(self, project_id: str, task: dict, current_fingerprint: str) -> dict:
        events = self.store.events(project_id, limit=1000, task_id=task["id"])
        implementation = [event for event in events if event["kind"] == "git"
                          and event["details"].get("has_visible_changes")]
        passed_tests = [event for event in events if event["kind"] == "test"
                        and event["details"].get("passed")
                        and event["fingerprint"] == current_fingerprint]
        if implementation and passed_tests:
            state = "completed_confirmed" if task["confirmed"] else "tests_passed"
        elif implementation:
            state = "implementation_observed"
        else:
            state = "planned"
        return {
            "id": task["id"], "title": task["title"], "state": state,
            "agent_claim": task["claim"], "confirmed_by_user": bool(task["confirmed"]),
            "implementation_event_ids": [event["id"] for event in implementation[:3]],
            "current_passing_test_event_ids": [event["id"] for event in passed_tests[:3]],
            "tests_are_current": bool(passed_tests),
        }

    def confirm_task(self, path: Path, task_id: str) -> dict:
        project = self._project(path)
        task = self._task(project["id"], task_id)
        observed = snapshot(Path(project["path"]))
        state = self._task_state(project["id"], task, observed.fingerprint)
        if state["state"] != "tests_passed":
            raise ValueError("A task needs observed changes and a current passing test before confirmation")
        self.store.confirm_task(task_id)
        self.store.add_event(
            project["id"], "confirmation", f"User confirmed task: {task['title']}",
            "explicit", "auto", task_id, observed.head, observed.fingerprint,
        )
        return self._task_state(project["id"], self._task(project["id"], task_id),
                                observed.fingerprint)

    def project_state(self, path: Path) -> dict:
        project = self._project(path)
        observed = snapshot(Path(project["path"]))
        tasks = [self._task_state(project["id"], task, observed.fingerprint)
                 for task in self.store.tasks(project["id"])]
        recent = self.store.events(project["id"], 8)
        checkpoint = self.store.latest_checkpoint(project["id"])
        return {
            "project": {"id": project["id"], "name": project["name"],
                        "path": project["path"]},
            "active_session": self.store.active_session(project["id"]),
            "git": {"head": observed.head, "fingerprint": observed.fingerprint,
                    "changed_paths": list(observed.changed_paths)},
            "tasks": tasks,
            "recent_events": [{"id": event["id"], "kind": event["kind"],
                               "summary": event["summary"], "source_ref": event["source_ref"],
                               "created_at": event["created_at"],
                               "session_id": event["session_id"]} for event in recent],
            "latest_checkpoint": ({"id": checkpoint["id"],
                                   "created_at": checkpoint["created_at"],
                                   "stale": checkpoint["fingerprint"] != observed.fingerprint}
                                  if checkpoint else None),
            "index": self.store.index_counts(project['id'], self.memory.embedder.model),
        }

    def index_memory(self, path: Path) -> dict:
        return self.memory.index_pending(self._project(path)["id"])

    def search_memory(self, path: Path, query: str, limit: int = 5,
                      allow_keyword_fallback: bool = True,
                      kind: str | None = None, keyword_only: bool = False,
                      hybrid: bool = False) -> dict:
        return self.memory.search(self._project(path)["id"], query, limit,
                                  allow_keyword_fallback, kind, keyword_only, hybrid)

    def recent_changes(self, path: Path, limit: int = 10) -> list[dict]:
        project = self._project(path)
        capped = min(max(limit, 1), 100)
        events = self.store.events(project["id"], 1000)
        return [event for event in events if event["kind"] == "git"][:capped]

    def task_history(self, path: Path, task_id: str) -> dict:
        project = self._project(path)
        task = self._task(project["id"], task_id)
        return {"task": task, "events": self.store.events(project["id"], 100, task_id)}

    def get_event(self, path: Path, event_id: str) -> dict:
        project = self._project(path)
        event = self.store.get_event(event_id)
        if not event or event["project_id"] != project["id"]:
            raise ValueError("Event was not found in this project")
        return event

    def create_checkpoint(self, path: Path) -> dict:
        project = self._project(path)
        state = self.project_state(path)
        payload = {"project": state["project"], "git": state["git"],
                   "tasks": state["tasks"], "recent_events": state["recent_events"],
                   "status": "candidate_unconfirmed"}
        return self.store.save_checkpoint(project["id"], state["git"]["fingerprint"], payload)
