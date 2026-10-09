"""Shared boundary for the memory and product tracks.

Developer 1 owns embedding and retrieval behavior. Developer 2 owns evidence
collection, persistence, and MCP/CLI. Keep these shapes stable across tracks.
"""

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

