"""Evidence rules and the stable service boundary used by CLI and MCP."""

import shlex
import subprocess
from pathlib import Path

from arc.git_evidence import snapshot
from arc.handoff import select_handoff_evidence
from arc.incidents import MIN_SEMANTIC_SIMILARITY, select_incident_matches
from arc.memory import Embedder, EmbeddingUnavailable, MemoryEngine, redact
from arc.store import Store, utc_now

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

    def _ensure_recording(self, project_id: str) -> None:
        if self.store.recording_paused(project_id):
            raise ValueError("Recording is paused for this project. Resume it before saving new evidence.")

    def list_projects(self) -> list[dict]:
        return [{"id": project["id"], "name": project["name"],
                 "path": project["path"],
                 "has_test_command": bool(project["test_command"])}
                for project in self.store.projects()]

    def recording_status(self, path: Path) -> dict:
        project = self._project(path)
        return {"recording_paused": self.store.recording_paused(project["id"]),
                "scope": "all new evidence for this project, including automatic observation"}

    def set_recording_paused(self, path: Path, paused: bool) -> dict:
        project = self._project(path)
        return self.store.set_recording_paused(project["id"], paused)

    def clear_project_memory(self, path: Path, confirmation: str) -> dict:
        project = self._project(path)
        if confirmation != f"DELETE {project['name']}":
            raise ValueError(f"Type DELETE {project['name']} to clear this project's A.R.C. memory")
        return self.store.clear_project_memory(project["id"])

    def _task(self, project_id: str, task_id: str) -> dict:
        task = self.store.get_task(task_id)
        if not task or task["project_id"] != project_id:
            raise ValueError("Task was not found in this project. Use the id from 'arc task add', "
                             "check 'arc state', and confirm ARC_DB selects the intended database.")
        return task

    def add_task(self, path: Path, title: str) -> dict:
        if not title.strip():
            raise ValueError("Task title must not be empty")
        project = self._project(path)
        self._ensure_recording(project["id"])
        return self.store.add_task(project["id"], redact(title.strip()))

    def start_session(self, path: Path, label: str = "Development session") -> dict:
        if not label.strip():
            raise ValueError("Session label must not be empty")
        project = self._project(path)
        self._ensure_recording(project["id"])
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
        self._ensure_recording(project["id"])
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

    def _incident(self, project_id: str, incident_id: str) -> dict:
        incident = self.store.get_incident(incident_id)
        if not incident or incident["project_id"] != project_id:
            raise ValueError("Incident was not found in this project")
        return incident

    def open_incident(self, path: Path, error_event_id: str,
                      cause: str | None = None) -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        error = self.get_event(path, error_event_id)
        if error["kind"] != "error":
            raise ValueError("An incident must start from a recorded error note")
        if cause is not None and not cause.strip():
            raise ValueError("Cause must not be empty")
        if self.store.incident_for_error(project["id"], error_event_id):
            raise ValueError("This error already has an incident")
        cleaned_cause = redact(cause.strip()) if cause else None
        cause_event = None
        if cleaned_cause:
            observed = snapshot(Path(project["path"]))
            cause_event = self.store.add_event(
                project["id"], "incident_cause", f"Recorded root cause: {cleaned_cause}",
                "explicit", "auto", git_head=observed.head,
                fingerprint=observed.fingerprint,
                details={"error_event_id": error_event_id},
            )
        incident = self.store.create_incident(
            project["id"], error_event_id, cleaned_cause,
            cause_event["id"] if cause_event else None,
        )
        return self.incident_history(path, incident["id"])

    def incident_history(self, path: Path, incident_id: str) -> dict:
        project = self._project(path)
        incident = self._incident(project["id"], incident_id)
        error = self.get_event(path, incident["error_event_id"])
        cause_event = (self.get_event(path, incident["cause_event_id"])
                       if incident["cause_event_id"] else None)
        current_fingerprint = snapshot(Path(project["path"])).fingerprint
        timeline = [{"role": "error", "event_id": error["id"],
                     "summary": error["summary"], "source_ref": error["source_ref"],
                     "created_at": error["created_at"], "outcome": None}]
        linked_tests = []
        resolution = None
        for link in self.store.incident_links(incident_id):
            event = self.get_event(path, link["event_id"])
            item = {"role": link["role"], "event_id": event["id"],
                    "summary": event["summary"], "source_ref": event["source_ref"],
                    "created_at": event["created_at"], "outcome": link["outcome"]}
            timeline.append(item)
            if link["role"] == "resolution":
                resolution = item
            if link["role"] == "test":
                linked_tests.append({**item, "current_passing":
                                     bool(event["details"].get("passed")
                                          and event["fingerprint"] == current_fingerprint)})
        return {"id": incident["id"], "project_id": project["id"],
                "status": "reported_resolved" if incident["resolved_at"] else "open",
                "cause": incident["cause"], "created_at": incident["created_at"],
                "cause_source_ref": cause_event["source_ref"] if cause_event else None,
                "resolved_at": incident["resolved_at"],
                "error": timeline[0], "timeline": timeline,
                "resolution": resolution, "linked_tests": linked_tests,
                "evidence_limit": "A reported resolution and a passing test do not prove this error is fixed."}

    def list_incidents(self, path: Path, limit: int = 20) -> list[dict]:
        project = self._project(path)
        incidents = self.store.incidents(project["id"], min(max(limit, 1), 100))
        result = []
        for incident in incidents:
            error = self.get_event(path, incident["error_event_id"])
            result.append({"id": incident["id"], "status": "reported_resolved"
                           if incident["resolved_at"] else "open",
                           "cause": incident["cause"], "error_summary": error["summary"],
                           "error_source_ref": error["source_ref"],
                           "cause_source_ref": (self.get_event(path, incident["cause_event_id"])["source_ref"]
                                                if incident["cause_event_id"] else None),
                           "created_at": incident["created_at"]})
        return result

    def add_incident_attempt(self, path: Path, incident_id: str, text: str,
                             outcome: str = "inconclusive") -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        incident = self._incident(project["id"], incident_id)
        if incident["resolved_at"]:
            raise ValueError("This incident is resolved; open a new incident for a new failure")
        if outcome not in {"failed", "inconclusive", "helped"}:
            raise ValueError("Attempt outcome must be failed, inconclusive, or helped")
        if not text.strip():
            raise ValueError("Attempt text must not be empty")
        observed = snapshot(Path(project["path"]))
        event = self.store.add_event(
            project["id"], "attempt", redact(text.strip()), "explicit", "auto",
            git_head=observed.head, fingerprint=observed.fingerprint,
            details={"incident_id": incident_id, "outcome": outcome},
        )
        self.store.link_incident_event(incident_id, event["id"], "attempt", outcome)
        return self.incident_history(path, incident_id)

    def link_incident_attempt(self, path: Path, incident_id: str,
                              attempt_event_id: str, outcome: str = "inconclusive") -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        incident = self._incident(project["id"], incident_id)
        if incident["resolved_at"]:
            raise ValueError("This incident is resolved; open a new incident for a new failure")
        if outcome not in {"failed", "inconclusive", "helped"}:
            raise ValueError("Attempt outcome must be failed, inconclusive, or helped")
        event = self.get_event(path, attempt_event_id)
        if event["kind"] != "attempt":
            raise ValueError("Only an attempt event can be linked as an attempt")
        if any(link["event_id"] == attempt_event_id
               for link in self.store.incident_links(incident_id)):
            raise ValueError("This attempt is already linked to the incident")
        self.store.link_incident_event(incident_id, attempt_event_id, "attempt", outcome)
        return self.incident_history(path, incident_id)

    def resolve_incident(self, path: Path, incident_id: str, text: str,
                         cause: str | None = None,
                         test_event_id: str | None = None) -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        incident = self._incident(project["id"], incident_id)
        if incident["resolved_at"]:
            raise ValueError("This incident already has a reported resolution")
        if not text.strip():
            raise ValueError("Resolution text must not be empty")
        if cause is not None and not cause.strip():
            raise ValueError("Cause must not be empty")
        observed = snapshot(Path(project["path"]))
        if test_event_id:
            test = self.get_event(path, test_event_id)
            if (test["kind"] != "test" or not test["details"].get("passed")
                    or test["fingerprint"] != observed.fingerprint
                    or not self.store.event_is_newer(test_event_id, incident["error_event_id"])):
                raise ValueError("Linked test must have passed after the error at the current Git fingerprint")
        event = self.store.add_event(
            project["id"], "resolution", redact(text.strip()), "explicit", "auto",
            git_head=observed.head, fingerprint=observed.fingerprint,
            details={"incident_id": incident_id, "test_event_id": test_event_id,
                     "cause": redact(cause.strip()) if cause else None},
        )
        self.store.link_incident_event(incident_id, event["id"], "resolution")
        if test_event_id:
            self.store.link_incident_event(incident_id, test_event_id, "test")
        if cause is not None:
            self.store.set_incident_cause(incident_id, redact(cause.strip()), event["id"])
        return self.incident_history(path, incident_id)

    def search_incidents(self, path: Path, query: str,
                         cause: str | None = None, limit: int = 5) -> dict:
        project = self._project(path)
        if not query.strip():
            raise ValueError("Incident query must not be empty")
        if cause is not None and not cause.strip():
            raise ValueError("Cause must not be empty")
        limit = min(max(limit, 1), 10)
        cleaned_query = redact(query.strip())
        search = self.memory.search(project["id"], cleaned_query, limit=20, kind="error")
        by_error = {}
        for hit in search["hits"]:
            incident = self.store.incident_for_error(project["id"], hit["event_id"])
            if incident:
                by_error[hit["event_id"]] = incident
        selected = select_incident_matches(
            search["hits"], search["mode"], by_error, cleaned_query, cause, limit,
        )
        for group in ("candidates", "different_causes"):
            for item in selected[group]:
                history = self.incident_history(path, item["incident_id"])
                item["cause"] = history["cause"]
                item["cause_source_ref"] = history["cause_source_ref"]
                item["status"] = history["status"]
                item["timeline"] = history["timeline"]
                item["linked_tests"] = history["linked_tests"]
                item["guidance"] = (
                    "Review the recorded resolution and evidence; this is not proof of the new error's cause"
                    if group == "candidates" and history["resolution"]
                    else "Inspect this incident; do not reuse its resolution as a confirmed fix"
                )
        return {"mode": search["mode"], "score_kind": search["score_kind"],
                "model": search.get("model"), "query": redact(query.strip()),
                "cause_query": redact(cause.strip()) if cause else None,
                "semantic_minimum": MIN_SEMANTIC_SIMILARITY,
                "indexed_records": search["indexed_records"],
                "pending_records": search["pending_records"],
                **selected, "scanned_error_hits": len(search["hits"]),
                "notice": search.get("notice") or search.get("reason"),
                "interpretation": "All results are candidates. Cause labels compare explicit text; similarity is not proof of a shared cause."}

    def capture_git(self, path: Path, task_id: str | None = None) -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
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
        self._ensure_recording(project["id"])
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

    def _task_evidence(self, project_id: str, task: dict,
                       current_fingerprint: str) -> dict:
        events = self.store.events(project_id, limit=1000, task_id=task["id"])
        correction_index = next((index for index, event in enumerate(events)
                                 if event["kind"] == "task_correction"), None)
        correction = events[correction_index] if correction_index is not None else None
        active_events = events[:correction_index] if correction_index is not None else events
        implementation = [
            event for event in active_events
            if event["kind"] == "git" and event["details"].get("has_visible_changes")
            and not (correction and correction["details"].get("to_state") == "planned"
                     and event["fingerprint"] == correction["fingerprint"])
        ]
        if correction and correction["details"].get("to_state") == "implementation_observed":
            anchor = self.store.get_event(correction["details"].get("implementation_event_id"))
            if (anchor and anchor["project_id"] == project_id and anchor["task_id"] == task["id"]
                    and anchor["kind"] == "git" and anchor["details"].get("has_visible_changes")
                    and all(event["id"] != anchor["id"] for event in implementation)):
                implementation.append(anchor)
        passed_tests = [event for event in active_events if event["kind"] == "test"
                        and event["details"].get("passed")
                        and event["fingerprint"] == current_fingerprint]
        confirmations = [event for event in active_events if event["kind"] == "confirmation"
                         and event["fingerprint"] == current_fingerprint]
        return {"events": events, "correction": correction,
                "implementation": implementation, "passed_tests": passed_tests,
                "confirmations": confirmations}

    def _task_state(self, project_id: str, task: dict, current_fingerprint: str) -> dict:
        evidence = self._task_evidence(project_id, task, current_fingerprint)
        implementation = evidence["implementation"]
        passed_tests = evidence["passed_tests"]
        confirmations = evidence["confirmations"]
        if implementation and passed_tests:
            state = "completed_confirmed" if confirmations else "tests_passed"
        elif implementation:
            state = "implementation_observed"
        else:
            state = "planned"
        correction = evidence["correction"]
        return {
            "id": task["id"], "title": task["title"], "state": state,
            "agent_claim": task["claim"], "confirmed_by_user": bool(confirmations),
            "implementation_event_ids": [event["id"] for event in implementation[:3]],
            "current_passing_test_event_ids": [event["id"] for event in passed_tests[:3]],
            "current_confirmation_event_ids": [event["id"] for event in confirmations[:3]],
            "tests_are_current": bool(passed_tests),
            "latest_correction": ({"id": correction["id"],
                                   "to_state": correction["details"]["to_state"],
                                   "reason": correction["details"]["reason"],
                                   "source_ref": correction["source_ref"],
                                   "created_at": correction["created_at"]}
                                  if correction else None),
        }

    def correct_task(self, path: Path, task_id: str, to_state: str, reason: str) -> dict:
        if to_state not in {"planned", "implementation_observed"}:
            raise ValueError("Correction can only set planned or implementation_observed")
        if not reason.strip():
            raise ValueError("A task correction needs a reason")
        project = self._project(path)
        self._ensure_recording(project["id"])
        task = self._task(project["id"], task_id)
        observed = snapshot(Path(project["path"]))
        before = self._task_state(project["id"], task, observed.fingerprint)
        anchor = before["implementation_event_ids"][0] if before["implementation_event_ids"] else None
        if to_state == "implementation_observed" and not anchor:
            raise ValueError("Implementation-observed needs a linked Git change")
        cleaned_reason = redact(reason.strip())
        self.store.add_event(
            project["id"], "task_correction",
            f"Task corrected to {to_state}: {cleaned_reason}", "explicit", "auto",
            task_id, observed.head, observed.fingerprint,
            {"from_state": before["state"], "to_state": to_state,
             "reason": cleaned_reason, "implementation_event_id": anchor
             if to_state == "implementation_observed" else None},
            set_task_confirmed=False,
        )
        return self._task_state(project["id"], self._task(project["id"], task_id),
                                observed.fingerprint)

    def task_review(self, path: Path, task_id: str) -> dict:
        project = self._project(path)
        task = self._task(project["id"], task_id)
        observed = snapshot(Path(project["path"]))
        current = self._task_state(project["id"], task, observed.fingerprint)
        evidence = self._task_evidence(project["id"], task, observed.fingerprint)
        active_ids = {event["id"] for group in ("implementation", "passed_tests", "confirmations")
                      for event in evidence[group]}
        current_test_ids = {event["id"] for event in evidence["passed_tests"]}
        correction_id = evidence["correction"]["id"] if evidence["correction"] else None
        correction_seen = False
        missing = []
        if not current["implementation_event_ids"]:
            missing.append(f"Capture a linked Git change with arc capture --task {task_id}")
        if not current["tests_are_current"]:
            missing.append(f"Run a passing configured test at the current Git state with arc test --task {task_id}")
        if current["state"] == "tests_passed":
            missing.append(f"Review the evidence, then confirm with arc task confirm {task_id}")
        recent = []
        for event in evidence["events"][:30]:
            if event["id"] == correction_id:
                correction_seen = True
            superseded = correction_seen and event["id"] != correction_id
            if event["id"] in active_ids:
                evidence_status = "counts_for_current_state"
            elif superseded:
                evidence_status = "superseded_by_correction"
            elif event["kind"] == "test" and not event["details"].get("passed"):
                evidence_status = "failed_test"
            elif event["kind"] in {"test", "confirmation"} and event["fingerprint"] != observed.fingerprint:
                evidence_status = "stale_git_state"
            elif (event["kind"] == "git" and evidence["correction"]
                  and evidence["correction"]["details"].get("to_state") == "planned"
                  and event["fingerprint"] == evidence["correction"]["fingerprint"]):
                evidence_status = "unchanged_since_correction"
            else:
                evidence_status = "recorded_context"
            recent.append({"id": event["id"], "kind": event["kind"],
                           "summary": event["summary"], "source_ref": event["source_ref"],
                           "created_at": event["created_at"],
                           "counts_for_current_state": event["id"] in active_ids,
                           "evidence_status": evidence_status,
                           "test_is_current": (event["kind"] == "test"
                                               and event["id"] in current_test_ids)})
        total_events = self.store.task_event_count(project["id"], task_id)
        return {"task": current, "current_git_fingerprint": observed.fingerprint,
                "requirements": {"observed_change": bool(current["implementation_event_ids"]),
                                 "current_passing_test": current["tests_are_current"],
                                 "current_confirmation": current["state"] == "completed_confirmed"},
                "missing": missing, "recent_evidence": recent,
                "shown_events": len(recent), "total_events": total_events,
                "has_more_events": total_events > len(recent)}

    def confirm_task(self, path: Path, task_id: str) -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        task = self._task(project["id"], task_id)
        observed = snapshot(Path(project["path"]))
        state = self._task_state(project["id"], task, observed.fingerprint)
        if state["state"] != "tests_passed":
            raise ValueError("A task needs observed changes and a current passing test before confirmation")
        self.store.add_event(
            project["id"], "confirmation", f"User confirmed task: {task['title']}",
            "explicit", "auto", task_id, observed.head, observed.fingerprint,
            set_task_confirmed=True,
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
            "recording": self.recording_status(path),
            "memory_index": self.store.index_counts(project["id"], self.memory.embedder.model),
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

    def project_handoff(self, path: Path, evidence_limit: int = 6) -> dict:
        if not 1 <= evidence_limit <= 12:
            raise ValueError("Handoff evidence limit must be between 1 and 12")
        project = self._project(path)
        state = self.project_state(path)
        events = self.store.events(project["id"], limit=1000)
        total_events = self.store.project_event_count(project["id"])
        recent_sessions = self.store.sessions(project["id"], limit=1)
        task_activity = {}
        for position, event in enumerate(events):
            if (event["task_id"] and event["task_id"] not in task_activity
                    and event["kind"] != "claim"):
                task_activity[event["task_id"]] = position

        priority = {"tests_passed": 3, "implementation_observed": 2, "planned": 1}
        unfinished = [task for task in state["tasks"]
                      if task["state"] != "completed_confirmed"]
        unfinished.sort(key=lambda task: (-priority[task["state"]],
                                          task_activity.get(task["id"], len(events) + 1),
                                          task["title"]))
        confirmed = [task for task in state["tasks"]
                     if task["state"] == "completed_confirmed"]
        confirmed.sort(key=lambda task: (task_activity.get(task["id"], len(events) + 1),
                                         task["title"]))

        def task_view(task: dict) -> dict:
            return {"id": task["id"], "title": task["title"], "state": task["state"],
                    "unverified_agent_claim": task["agent_claim"],
                    "implementation_refs": [f"arc:event/{event_id}" for event_id in
                                            task["implementation_event_ids"]],
                    "current_passing_test_refs": [f"arc:event/{event_id}" for event_id in
                                                  task["current_passing_test_event_ids"]],
                    "current_confirmation_refs": [f"arc:event/{event_id}" for event_id in
                                                  task["current_confirmation_event_ids"]],
                    "latest_correction": task["latest_correction"]}

        selected = select_handoff_evidence(
            events, {task["id"] for task in unfinished},
            state["git"]["fingerprint"], evidence_limit,
        )
        suggested = None
        if unfinished:
            task = unfinished[0]
            next_step = {
                "tests_passed": f"Review evidence and confirm task {task['id']} if complete",
                "implementation_observed": f"Run the configured test for task {task['id']}",
                "planned": f"Implement task {task['id']} and capture its Git change",
            }[task["state"]]
            suggested = {"id": task["id"], "title": task["title"],
                         "state": task["state"], "next_step": next_step,
                         "selection_reason": "Highest-priority unfinished task by current evidence and recent activity; not explicitly marked active"}
        checkpoint = state["latest_checkpoint"]
        return {
            "status": "recorded_context" if total_events else "no_recorded_events",
            "generated_at_utc": utc_now(), "project": state["project"],
            "git": state["git"], "active_session": state["active_session"],
            "latest_session": recent_sessions[0] if recent_sessions else None,
            "overview": (f"{len(unfinished)} unfinished task(s), "
                         f"{len(confirmed)} currently confirmed task(s), "
                         f"{len(selected)} selected evidence item(s)."),
            "suggested_next_task": suggested,
            "unfinished_tasks": [task_view(task) for task in unfinished[:8]],
            "total_unfinished_tasks": len(unfinished),
            "confirmed_tasks": [task_view(task) for task in confirmed[:3]],
            "total_confirmed_tasks": len(confirmed),
            "key_evidence": selected,
            "latest_checkpoint": ({**checkpoint, "status": "candidate_unconfirmed"}
                                  if checkpoint else None),
            "history_window": {"scanned_events": len(events),
                               "total_events": total_events,
                               "truncated": total_events > len(events)},
            "limits": ["Only explicitly recorded project events are considered.",
                       "Claims and attempts do not prove completion or resolution."],
        }

    def index_memory(self, path: Path) -> dict:
        return self.memory.index_pending(self._project(path)["id"])

    def local_ai_status(self) -> dict:
        from arc.chat import OllamaChat
        model = self.memory.embedder.model
        try:
            vector = self.memory.embedder.embed("A.R.C. local AI status")
            status = {"status": "ready", "model": model,
                      "vector_dimensions": len(vector), "local_only": True}
        except EmbeddingUnavailable as error:
            status = {"status": "unavailable", "model": model,
                      "reason": str(error), "local_only": True}
        status["chat"] = OllamaChat().probe()
        return status

    def project_timeline(self, path: Path, limit: int = 40, offset: int = 0,
                         kind: str | None = None) -> dict:
        project = self._project(path)
        limit = min(max(limit, 1), 100)
        offset = max(offset, 0)
        page = self.store.timeline(project["id"], limit, offset, kind)
<<<<<<< HEAD
=======
        if isinstance(page, tuple):
            events, total = page
        else:
            events, total = page["events"], page["total_events"]
>>>>>>> 41fec2987a1aa4127cfad99200827343cc54cd7e
        return {"events": [{"id": event["id"], "kind": event["kind"],
                            "summary": event["summary"], "source": event["source"],
                            "source_ref": event["source_ref"],
                            "created_at": event["created_at"],
                            "task_id": event["task_id"],
                            "session_id": event["session_id"]} for event in page["events"]],
                "total": page["total_events"], "offset": offset, "limit": limit,
                "has_more": page["next_offset"] is not None}

    def checkpoint_history(self, path: Path, limit: int = 20) -> list[dict]:
        project = self._project(path)
        current_fingerprint = snapshot(Path(project["path"])).fingerprint
        checkpoints = self.store.checkpoints(project["id"], min(max(limit, 1), 100))
        return [{"id": item["id"], "created_at": item["created_at"],
                 "stale": item["fingerprint"] != current_fingerprint,
                 "status": "candidate_unconfirmed", "payload": item["payload"]}
                for item in checkpoints]

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
        observed = snapshot(Path(project["path"]))
        return {"task": task,
                "current_state": self._task_state(project["id"], task, observed.fingerprint),
                "events": self.store.events(project["id"], 100, task_id)}

    def get_event(self, path: Path, event_id: str) -> dict:
        project = self._project(path)
        event = self.store.get_event(event_id)
        if not event or event["project_id"] != project["id"]:
            raise ValueError("Event was not found in this project")
        return event

    def create_checkpoint(self, path: Path) -> dict:
        project = self._project(path)
        self._ensure_recording(project["id"])
        state = self.project_state(path)
        payload = {"project": state["project"], "git": state["git"],
                   "tasks": state["tasks"], "recent_events": state["recent_events"],
                   "status": "candidate_unconfirmed"}
        return self.store.save_checkpoint(project["id"], state["git"]["fingerprint"], payload)
