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
        "before making changes. Checkpoint creation saves an unconfirmed candidate."
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
def arc_search_memory(query: str, limit: int = 5) -> dict:
    """Find project memories by local semantic search, with labelled keyword fallback."""
    service, project = _service()
    try:
        return service.search_memory(project, query, limit)
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
