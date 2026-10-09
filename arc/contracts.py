"""Stable data shapes shared by evidence collection and local retrieval."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitSnapshot:
    root: Path
    head: str
    fingerprint: str
    changed_paths: tuple[str, ...]


@dataclass(frozen=True)
class SearchHit:
    event_id: str
    kind: str
    summary: str
    source_ref: str
    created_at: str
    score: float


TASK_STATES = (
    "planned", "implementation_observed", "tests_passed", "completed_confirmed"
)

