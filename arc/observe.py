"""Opt-in file and Git observation for one explicitly registered project.

The worker polls a Git repository with the standard library only. It records
stable file changes and new commits as deduplicated events and stores paths,
hashes, and evidence references -- never file contents. Pausing recording
suspends collection, and resuming always establishes a fresh baseline so
deliberately unrecorded activity is not silently imported.
"""

import hashlib
import os
import sqlite3
import sys
import time
from pathlib import Path

from arc.git_evidence import (
    _git,
    _visible,
    commit_subject,
    commits_between,
    current_branch,
    current_head,
    is_ancestor,
    snapshot,
)
from arc.memory import redact
from arc.store import Store

IGNORED_DIRS = frozenset({
    ".git", ".arc", ".idea", ".vscode", "node_modules", "__pycache__",
    ".venv", "venv", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build", "target", "coverage", ".next", "out",
})
POLL_SECONDS = 1.5
SETTLE_SECONDS = 1.5
GIT_SECONDS = 15.0
HEARTBEAT_SECONDS = 5.0
MAX_HASH_BYTES = 2 * 1024 * 1024
COMMIT_CATCHUP_LIMIT = 200


def list_project_files(root: Path) -> list[str]:
    """Tracked and untracked non-ignored files, minus generated/sensitive paths."""
    raw = _git(root, "ls-files", "-co", "--exclude-standard", "-z")
    result = []
    for name in raw.decode("utf-8", "surrogateescape").split("\0"):
        if not name:
            continue
        rel = name.replace("\\", "/")
        if any(part in IGNORED_DIRS for part in rel.split("/")[:-1]):
            continue
        if _visible(rel):
            result.append(rel)
    return result


def file_signature(path: Path) -> tuple[int, int] | None:
    try:
        info = path.lstat()
    except OSError:
        return None
    return (info.st_mtime_ns, info.st_size)


def file_state(path: Path, signature: tuple[int, int] | None) -> str:
    """Stable content identity for deduplication; the content itself is not stored."""
    if signature is None:
        return "deleted"
    if path.is_symlink():
        try:
            target = os.readlink(path).encode("utf-8", "surrogateescape")
        except OSError:
            return "deleted"
        return "link:" + hashlib.sha256(target).hexdigest()
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            if signature[1] <= MAX_HASH_BYTES:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
            else:
                # Large files: hash size plus the first and last 64 KB.
                digest.update(str(signature[1]).encode())
                digest.update(source.read(65536))
                source.seek(max(65536, signature[1] - 65536))
                digest.update(source.read(65536))
    except OSError:
        return "deleted"
    return "sha256:" + digest.hexdigest()


class Observer:
    """Polling worker for one project; driven by tick() so tests can step it."""

    def __init__(self, store: Store, project: dict,
                 poll_seconds: float = POLL_SECONDS,
                 settle_seconds: float = SETTLE_SECONDS,
                 git_seconds: float = GIT_SECONDS,
                 on_event=None):
        self.store = store
        self.project = project
        self.root = Path(project["path"])
        self.poll_seconds = poll_seconds
        self.settle_seconds = settle_seconds
        self.git_seconds = git_seconds
        self.on_event = on_event
        self.states: dict[str, str | None] = {}
        self._sigs: dict[str, tuple[int, int]] = {}
        self.pending: dict[str, dict] = {}
        self._paused = False
        self._session_id: str | None = None
        self._last_git = 0.0
        self._last_heartbeat = 0.0

    def _emit(self, kind: str, summary: str, git_head: str | None = None,
              fingerprint: str | None = None, details: dict | None = None,
              dedup_key: str | None = None) -> dict:
        event = self.store.add_event(
            self.project["id"], kind, summary, "watcher", "auto",
            git_head=git_head, fingerprint=fingerprint, details=details,
            dedup_key=dedup_key,
        )
        if self.on_event:
            self.on_event(event)
        return event

    def _baseline_files(self) -> None:
        """Snapshot current file signatures without recording any event."""
        self._sigs = {}
        self.states = {}
        for rel in list_project_files(self.root):
            signature = file_signature(self.root / rel)
            if signature is None:
                continue
            self._sigs[rel] = signature
            self.states[rel] = None
        self.pending.clear()

    def baseline(self) -> None:
        """Fresh baseline: current files plus the current commit cursor."""
        self._baseline_files()
        self.store.set_observation_cursor(
            self.project["id"], current_head(self.root), current_branch(self.root)
        )

    def scan_files(self, now: float | None = None) -> None:
        """One scan/flush pass over project files with save-burst coalescing."""
        now = time.monotonic() if now is None else now
        seen: dict[str, tuple[int, int]] = {}
        for rel in list_project_files(self.root):
            signature = file_signature(self.root / rel)
            if signature is not None:
                seen[rel] = signature
        for rel, signature in seen.items():
            if self._sigs.get(rel) != signature:
                self._sigs[rel] = signature
                self.pending[rel] = {"sig": signature, "since": now}
        for rel in [rel for rel in self._sigs if rel not in seen]:
            del self._sigs[rel]
            if rel in self.states:
                self.pending[rel] = {"sig": None, "since": now}
        self._flush(now)

    def _flush(self, now: float) -> None:
        due = [rel for rel, item in self.pending.items()
               if now - item["since"] >= self.settle_seconds]
        if not due:
            return
        snap = None
        for rel in due:
            item = self.pending[rel]
            signature = file_signature(self.root / rel)
            if signature != item["sig"]:
                item["sig"] = signature
                item["since"] = now
                if signature is None:
                    self._sigs.pop(rel, None)
                else:
                    self._sigs[rel] = signature
                continue
            state = file_state(self.root / rel, signature)
            previous = self.states.get(rel)
            del self.pending[rel]
            if previous == state:
                continue
            if state == "deleted" and rel not in self.states:
                continue
            if rel not in self.states or previous == "deleted":
                change = "created"
            elif state == "deleted":
                change = "deleted"
            else:
                change = "modified"
            if snap is None:
                snap = snapshot(self.root)
            self.states[rel] = state
            self._emit(
                "file_change", f"File {change}: {rel}",
                git_head=snap.head, fingerprint=snap.fingerprint,
                details={"path": rel, "change": change, "content_state": state},
                dedup_key=f"watch:file:{rel}:{state}",
            )

    def check_git(self) -> None:
        """Reconcile the persisted commit cursor with the current Git HEAD."""
        project_id = self.project["id"]
        state = self.store.observation_state(project_id)
        head = current_head(self.root)
        branch = current_branch(self.root)
        cursor = state["cursor_head"]
        if cursor == head:
            if state["cursor_branch"] != branch:
                self.store.set_observation_cursor(project_id, head, branch)
            return
        if not cursor or cursor == "UNBORN" or head == "UNBORN":
            self.baseline()
            return
        if is_ancestor(self.root, cursor, head):
            shas = commits_between(self.root, cursor, head, COMMIT_CATCHUP_LIMIT + 1)
            truncated = len(shas) > COMMIT_CATCHUP_LIMIT
            for sha in shas[:COMMIT_CATCHUP_LIMIT]:
                subject = redact(commit_subject(self.root, sha))[:200]
                self._emit(
                    "commit", f"Commit {sha[:12]}: {subject}", git_head=sha,
                    details={"commit": sha, "branch": branch, "subject": subject},
                    dedup_key=f"watch:commit:{sha}",
                )
            if truncated:
                self._emit(
                    "observation",
                    f"More than {COMMIT_CATCHUP_LIMIT} commits since the recorded "
                    f"cursor; only the oldest {COMMIT_CATCHUP_LIMIT} were listed",
                    git_head=head,
                    details={"cursor": cursor, "head": head, "truncated": True},
                    dedup_key=f"watch:commit-overflow:{cursor}:{head}",
                )
        else:
            self._emit(
                "observation",
                f"Git HEAD moved to {branch or 'detached'} {head[:12]}",
                git_head=head,
                details={"head": head, "branch": branch, "previous_cursor": cursor,
                         "note": "HEAD moved without a fast-forward; intermediate "
                                 "commits may not be listed"},
                dedup_key=f"watch:head:{head}:{branch or 'detached'}",
            )
        self.store.set_observation_cursor(project_id, head, branch)

    def start(self) -> None:
        project_id = self.project["id"]
        self._session_id = self.store.start_observation_session(project_id)["id"]
        self.store.set_observation_worker(project_id, os.getpid(), self._session_id)
        self._emit("observation",
                   f"Observation worker started (pid {os.getpid()})",
                   git_head=current_head(self.root),
                   details={"action": "started", "worker_pid": os.getpid()})
        if self.store.recording_paused(project_id):
            self._paused = True
            return
        if self.store.observation_state(project_id)["cursor_head"]:
            # Restart: recover commits made while no worker was running.
            self.check_git()
            self._baseline_files()
        else:
            self.baseline()
        self._last_git = time.monotonic()

    def tick(self) -> bool:
        """One worker cycle; returns False once observation is disabled."""
        project_id = self.project["id"]
        if not self.store.observation_state(project_id)["enabled"]:
            return False
        now = time.monotonic()
        if now - self._last_heartbeat >= HEARTBEAT_SECONDS:
            self._last_heartbeat = now
            self.store.heartbeat_observation(project_id, os.getpid())
        if self.store.recording_paused(project_id):
            self._paused = True
            return True
        if self._paused:
            self._paused = False
            self.baseline()
            return True
        self.scan_files(now)
        if now - self._last_git >= self.git_seconds:
            self._last_git = now
            self.check_git()
        return True

    def stop(self) -> None:
        project_id = self.project["id"]
        try:
            self.store.set_observation_worker(project_id, None)
            if self._session_id:
                self.store.finish_observation_session(self._session_id)
                self._session_id = None
            self._emit("observation", "Observation worker stopped",
                       git_head=current_head(self.root),
                       details={"action": "stopped", "worker_pid": os.getpid()})
        except (sqlite3.Error, ValueError, OSError):
            pass

    def run(self, max_ticks: int | None = None) -> None:
        self.start()
        ticks = 0
        try:
            while self.tick():
                ticks += 1
                if max_ticks is not None and ticks >= max_ticks:
                    break
                time.sleep(self.poll_seconds)
        except KeyboardInterrupt:
            pass
        finally:
            self.stop()


def run_worker(store: Store, project: dict, poll_seconds: float = POLL_SECONDS) -> None:
    def log(event: dict) -> None:
        print(f"arc watch [{event['created_at']}] {event['kind']}: {event['summary']}",
              flush=True)

    print(f"A.R.C.: watching {project['path']} (Ctrl+C to stop)",
          file=sys.stderr, flush=True)
    Observer(store, project, poll_seconds=poll_seconds, on_event=log).run()
