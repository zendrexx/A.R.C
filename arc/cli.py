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
    correct = task_commands.add_parser("correct", help="record a downward status correction")
    correct.add_argument("task_id")
    correct.add_argument("--to", required=True,
                         choices=("planned", "implementation_observed"))
    correct.add_argument("--reason", required=True)
    task_commands.add_parser("review", help="show current verification evidence").add_argument(
        "task_id"
    )
    task_commands.add_parser("history").add_argument("task_id")

    incident = commands.add_parser("incident", help="link errors, attempts, and resolutions")
    incident_commands = incident.add_subparsers(dest="incident_command", required=True)
    opened = incident_commands.add_parser("open", help="start from a recorded error event")
    opened.add_argument("error_event_id")
    opened.add_argument("--cause", help="explicit root cause, if known")
    incident_commands.add_parser("list", help="list recorded incidents")
    incident_commands.add_parser("show", help="show linked history").add_argument("incident_id")
    attempt = incident_commands.add_parser("attempt", help="record and link a debugging attempt")
    attempt.add_argument("incident_id")
    attempt.add_argument("text")
    attempt.add_argument("--outcome", choices=("failed", "inconclusive", "helped"),
                         default="inconclusive")
    linked = incident_commands.add_parser("link-attempt", help="link an existing attempt note")
    linked.add_argument("incident_id")
    linked.add_argument("attempt_event_id")
    linked.add_argument("--outcome", choices=("failed", "inconclusive", "helped"),
                        default="inconclusive")
    resolved = incident_commands.add_parser("resolve", help="report a resolution with optional test")
    resolved.add_argument("incident_id")
    resolved.add_argument("text")
    resolved.add_argument("--cause")
    resolved.add_argument("--test-event", dest="test_event_id")
    incident_search = incident_commands.add_parser("search", help="find related prior incidents")
    incident_search.add_argument("query")
    incident_search.add_argument("--cause", help="explicit cause of the new error, if known")
    incident_search.add_argument("--limit", type=int, default=5)

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
    search.add_argument("--kind", help="only return this event type, e.g. error or decision")
    search_modes = search.add_mutually_exclusive_group()
    search_modes.add_argument("--semantic-only", action="store_true")
    search_modes.add_argument("--keyword-only", action="store_true")
    search_modes.add_argument("--hybrid", action="store_true")
    commands.add_parser("state", help="show evidence-backed project state")
    handoff = commands.add_parser("handoff", help="show a compact evidence-linked handoff")
    handoff.add_argument("--limit", type=int, default=6,
                         help="maximum selected evidence items, 1–12")
    commands.add_parser("event", help="inspect one evidence record").add_argument("event_id")
    commands.add_parser("checkpoint", help="store an unconfirmed handoff checkpoint")
    dashboard = commands.add_parser("dashboard", help="open the local project dashboard")
    dashboard.add_argument("--port", type=int, default=8765)
    dashboard.add_argument("--no-browser", action="store_true")
    commands.add_parser("serve", help="run the local stdio MCP server")
    observer = commands.add_parser('observer', help='control opt-in local collection')
    observer.add_argument('action', choices=['status', 'enable', 'pause', 'resume',
                                           'disable', 'poll', 'start', 'stop'])
    watch = commands.add_parser('watch', help='run an enabled project observer until stopped')
    watch.add_argument('--interval', type=float, default=5,
                       help='seconds between Git polls (default: 5)')
    timeline = commands.add_parser('timeline', help='inspect paginated recorded activity')
    timeline.add_argument('--kind')
    timeline.add_argument('--since')
    timeline.add_argument('--until')
    timeline.add_argument('--offset', type=int, default=0)
    timeline.add_argument('--snapshot', type=int, help='snapshot_rowid returned by the first page')
    ask = commands.add_parser('chat', help='answer from local, cited project evidence')
    ask.add_argument('question')
    ask.add_argument('--timezone-offset', type=int, default=0, help='local UTC offset in minutes')
    ask.add_argument('--offset', type=int, default=0)
    ask.add_argument('--snapshot', type=int, help='snapshot_rowid returned by the first page')
    ask.add_argument('--keyword-only', action='store_true')
    return parser


def main(argv: list[str] | None = None) -> int:
    # CLI JSON is a UTF-8 contract even when Windows pipes default to a legacy code page.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, 'reconfigure'):
            stream.reconfigure(encoding='utf-8')
    args = build_parser().parse_args(argv)
    project_path = args.project.expanduser().resolve()
    db_path = args.db.expanduser().resolve()
    if args.command == "serve":
        os.environ["ARC_PROJECT"] = str(project_path)
        os.environ["ARC_DB"] = str(db_path)
        from arc.mcp_server import mcp
        mcp.run()
        return 0
    if args.command == "dashboard":
        from arc.dashboard import run_dashboard
        try:
            run_dashboard(db_path, args.port, not args.no_browser, project_path)
            return 0
        except OSError as error:
            print(f"A.R.C.: Dashboard could not start: {error}", file=sys.stderr)
            return 2

    service = ArcService(db_path)
    try:
        if args.command == "init":
            result = service.register_project(project_path, args.test_command)
        elif args.command == 'observer':
            from arc.observer import status, control, poll, launch, stop_worker
            if args.action == 'status':
                result = status(service, project_path)
            elif args.action == 'poll':
                result = poll(service, project_path)
            elif args.action == 'start':
                result = launch(service, project_path)
            elif args.action == 'stop':
                result = stop_worker(service, project_path)
            else:
                result = control(service, project_path, args.action)
        elif args.command == 'watch':
            from arc.observer import watch
            watch(service, project_path, interval=args.interval)
            return 0
        elif args.command == 'timeline':
            result = service.store.timeline(service._project(project_path)['id'],
                offset=max(0, args.offset), kind=args.kind, since=args.since, until=args.until,
                snapshot_rowid=args.snapshot)
        elif args.command == 'chat':
            from arc.chat import answer
            result = answer(service, project_path, args.question, args.timezone_offset,
                            args.keyword_only, args.offset, snapshot_rowid=args.snapshot)
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
            elif args.task_command == "correct":
                result = service.correct_task(project_path, args.task_id, args.to, args.reason)
            elif args.task_command == "review":
                result = service.task_review(project_path, args.task_id)
            else:
                result = service.task_history(project_path, args.task_id)
        elif args.command == "incident":
            if args.incident_command == "open":
                result = service.open_incident(project_path, args.error_event_id, args.cause)
            elif args.incident_command == "list":
                result = service.list_incidents(project_path)
            elif args.incident_command == "show":
                result = service.incident_history(project_path, args.incident_id)
            elif args.incident_command == "attempt":
                result = service.add_incident_attempt(
                    project_path, args.incident_id, args.text, args.outcome
                )
            elif args.incident_command == "link-attempt":
                result = service.link_incident_attempt(
                    project_path, args.incident_id, args.attempt_event_id, args.outcome
                )
            elif args.incident_command == "resolve":
                result = service.resolve_incident(
                    project_path, args.incident_id, args.text, args.cause, args.test_event_id
                )
            else:
                result = service.search_incidents(
                    project_path, args.query, args.cause, args.limit
                )
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
                                           allow_keyword_fallback=not args.semantic_only,
                                           kind=args.kind, keyword_only=args.keyword_only,
                                           hybrid=args.hybrid)
        elif args.command == "state":
            result = service.project_state(project_path)
        elif args.command == "handoff":
            result = service.project_handoff(project_path, args.limit)
        elif args.command == "event":
            result = service.get_event(project_path, args.event_id)
        else:
            result = service.create_checkpoint(project_path)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except KeyboardInterrupt:
        return 0
    except (ValueError, EmbeddingUnavailable, OSError) as error:
        print(f"A.R.C.: {error}", file=sys.stderr)
        return 2
    finally:
        service.close()


if __name__ == "__main__":
    raise SystemExit(main())

