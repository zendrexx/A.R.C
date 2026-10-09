"""Small local CLI for explicit evidence collection and handoff."""

import argparse
import json
import os
import sys
from pathlib import Path

from arc.memory import EmbeddingUnavailable
from arc.service import ArcService


def default_database() -> Path:
    configured = os.environ.get("ARC_DB")
    if configured:
        return Path(configured)
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "A.R.C" / "arc.sqlite3"
    return Path.home() / ".local" / "share" / "arc" / "arc.sqlite3"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="arc", description="Local project memory")
    parser.add_argument("--project", type=Path, default=Path.cwd(),
                        help="selected Git project (default: current folder)")
    parser.add_argument("--db", type=Path, default=default_database(),
                        help="local SQLite file (default: user application data folder)")
    commands = parser.add_subparsers(dest="command", required=True)
    init = commands.add_parser("init", help="register a Git project")
    init.add_argument("--test-command", help="approved executable and arguments, no shell syntax")

    session = commands.add_parser("session", help="group recorded events into a work session")
    session_commands = session.add_subparsers(dest="session_command", required=True)
    session_commands.add_parser("start", help="begin a session").add_argument(
        "label", nargs="?", default="Development session"
    )
    session_commands.add_parser("end", help="end the active session")
    session_commands.add_parser("status", help="show the active session")
    session_commands.add_parser("list", help="list recent sessions")
    session_commands.add_parser("show", help="show a session and its events").add_argument(
        "session_id"
    )

    task = commands.add_parser("task", help="record or inspect an explicit task")
    task_commands = task.add_subparsers(dest="task_command", required=True)
    task_commands.add_parser("add").add_argument("title")
    claim = task_commands.add_parser("claim", help="record an unverified claim")
    claim.add_argument("task_id")
    claim.add_argument("text")
    task_commands.add_parser("confirm", help="confirm current tested work").add_argument("task_id")
    task_commands.add_parser("history").add_argument("task_id")

    note = commands.add_parser("note", help="store an explicit development memory")
    note.add_argument("text")
    note.add_argument("--kind", choices=("note", "decision", "attempt", "error"), default="note")
    note.add_argument("--task", dest="task_id")
    capture = commands.add_parser("capture", help="record current Git metadata")
    capture.add_argument("--task", dest="task_id")
    test = commands.add_parser("test", help="run the configured test command and save its result")
    test.add_argument("--task", dest="task_id")
    commands.add_parser("index", help="embed pending records through local Ollama")
    search = commands.add_parser("search", help="search local memory")
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=5)
    search.add_argument("--semantic-only", action="store_true")
    commands.add_parser("state", help="show evidence-backed project state")
    commands.add_parser("event", help="inspect one evidence record").add_argument("event_id")
    commands.add_parser("checkpoint", help="store an unconfirmed handoff checkpoint")
    commands.add_parser("serve", help="run the local stdio MCP server")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    project_path = args.project.expanduser().resolve()
    db_path = args.db.expanduser().resolve()
    if args.command == "serve":
        os.environ["ARC_PROJECT"] = str(project_path)
        os.environ["ARC_DB"] = str(db_path)
        from arc.mcp_server import mcp
        mcp.run()
        return 0

    service = ArcService(db_path)
    try:
        if args.command == "init":
            result = service.register_project(project_path, args.test_command)
        elif args.command == "session":
            if args.session_command == "start":
                result = service.start_session(project_path, args.label)
            elif args.session_command == "end":
                result = service.end_session(project_path)
            elif args.session_command == "status":
                result = service.active_session(project_path)
            elif args.session_command == "list":
                result = service.sessions(project_path)
            else:
                result = service.session_history(project_path, args.session_id)
        elif args.command == "task":
            if args.task_command == "add":
                result = service.add_task(project_path, args.title)
            elif args.task_command == "claim":
                result = service.record_note(project_path, "claim", args.text, args.task_id)
            elif args.task_command == "confirm":
                result = service.confirm_task(project_path, args.task_id)
            else:
                result = service.task_history(project_path, args.task_id)
        elif args.command == "note":
            result = service.record_note(project_path, args.kind, args.text, args.task_id)
        elif args.command == "capture":
            result = service.capture_git(project_path, args.task_id)
        elif args.command == "test":
            result = service.run_test(project_path, args.task_id)
        elif args.command == "index":
            result = service.index_memory(project_path)
        elif args.command == "search":
            result = service.search_memory(project_path, args.query, args.limit,
                                           allow_keyword_fallback=not args.semantic_only)
        elif args.command == "state":
            result = service.project_state(project_path)
        elif args.command == "event":
            result = service.get_event(project_path, args.event_id)
        else:
            result = service.create_checkpoint(project_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except (ValueError, EmbeddingUnavailable, OSError) as error:
        print(f"A.R.C.: {error}", file=sys.stderr)
        return 2
    finally:
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())

