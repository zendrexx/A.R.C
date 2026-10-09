"""Codex/other local agents access project memory through stdio MCP."""

import os
from pathlib import Path

from mcp.server.mcpserver import MCPServer
from mcp.types import ToolAnnotations

from arc.service import ArcService

mcp = MCPServer(
    "A.R.C.",
    instructions=(
        "This server reports selected local project evidence. Agent claims are unverified; "
        "passing tests apply only to their recorded project fingerprint. Reinspect current files "
        "before making changes. Use arc_get_project_handoff for a compact fresh-session view "
        "and inspect its source references. Use arc_search_incidents for prior error candidates; "
        "similarity and reported resolutions do not prove a shared cause or fix. "
        "Checkpoint creation saves an unconfirmed candidate."
    ),
)
READ_ONLY = ToolAnnotations(read_only_hint=True, destructive_hint=False, open_world_hint=False)
LOCAL_WRITE = ToolAnnotations(read_only_hint=False, destructive_hint=False,
                              idempotent_hint=False, open_world_hint=False)


def _service() -> tuple[ArcService, Path]:
    project = os.environ.get("ARC_PROJECT")
    database = os.environ.get("ARC_DB")
    if not project or not database:
        raise ValueError("Set ARC_PROJECT and ARC_DB for the MCP server")
    return ArcService(Path(database)), Path(project)


@mcp.tool(annotations=READ_ONLY)
def arc_get_project_state() -> dict:
    """Get current tasks, Git evidence, and checkpoint freshness for this project."""
    service, project = _service()
    try:
        return service.project_state(project)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_project_handoff(evidence_limit: int = 6) -> dict:
    """Get unfinished work and selected decisions, failures, and attempts with evidence IDs."""
    service, project = _service()
    try:
        return service.project_handoff(project, evidence_limit)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_search_memory(query: str, limit: int = 5,
                      kind: str | None = None, keyword_only: bool = False,
                      semantic_only: bool = False, hybrid: bool = False) -> dict:
    """Search project evidence with optional event type and retrieval mode."""
    service, project = _service()
    try:
        return service.search_memory(project, query, limit,
                                     allow_keyword_fallback=not semantic_only,
                                     kind=kind, keyword_only=keyword_only,
                                     hybrid=hybrid)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_recent_changes(limit: int = 10) -> list[dict]:
    """Get Git observations previously recorded for this project."""
    service, project = _service()
    try:
        return service.recent_changes(project, limit)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_task_history(task_id: str) -> dict:
    """Get a task's claims, observed changes, and recorded test evidence."""
    service, project = _service()
    try:
        return service.task_history(project, task_id)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_task_review(task_id: str) -> dict:
    """Review current task status, supporting evidence, and missing checks."""
    service, project = _service()
    try:
        return service.task_review(project, task_id)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_session_history(session_id: str) -> dict:
    """Get the time range and recorded evidence for one development session."""
    service, project = _service()
    try:
        return service.session_history(project, session_id)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_event(event_id: str) -> dict:
    """Inspect an evidence record returned by project state or memory search."""
    service, project = _service()
    try:
        return service.get_event(project, event_id)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_incident(incident_id: str) -> dict:
    """Read an explicitly linked error, attempt, resolution, and test history."""
    service, project = _service()
    try:
        return service.incident_history(project, incident_id)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_list_incidents(limit: int = 20) -> list[dict]:
    """List this project's recorded incidents with error source references."""
    service, project = _service()
    try:
        return service.list_incidents(project, limit)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_search_incidents(query: str, cause: str | None = None,
                         limit: int = 5) -> dict:
    """Find prior incident candidates; different recorded causes stay separate."""
    service, project = _service()
    try:
        return service.search_incidents(project, query, cause, limit)
    finally:
        service.close()


@mcp.tool(annotations=READ_ONLY)
def arc_get_observation_status() -> dict:
    """Get automatic observation state, worker heartbeat, and the Git commit cursor."""
    service, project = _service()
    try:
        return service.observation_status(project)
    finally:
        service.close()


@mcp.tool(annotations=LOCAL_WRITE)
def arc_create_checkpoint() -> dict:
    """Save an unconfirmed candidate handoff from current recorded evidence."""
    service, project = _service()
    try:
        return service.create_checkpoint(project)
    finally:
        service.close()


if __name__ == "__main__":
    mcp.run()
