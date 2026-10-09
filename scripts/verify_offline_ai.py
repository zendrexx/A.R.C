"""Check local semantic search, cited chat, and a fresh MCP session.

Run after downloading both Ollama models. Use --require-wifi-off for a physical
offline trial; the caller is responsible for restoring the network afterward.
"""

import argparse
import asyncio
import json
import os
import platform
import socket
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter


def run_cli(project: Path, database: Path, *arguments: str) -> dict:
    result = subprocess.run(
        [sys.executable, "-m", "arc.cli", "--project", str(project),
         "--db", str(database), *arguments],
        cwd=project, capture_output=True, text=True, check=True, timeout=75,
    )
    return json.loads(result.stdout)


async def check_mcp(project: Path, database: Path, event_id: str) -> None:
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    parameters = StdioServerParameters(
        command=sys.executable, args=["-m", "arc.mcp_server"],
        env={**os.environ, "ARC_PROJECT": str(project), "ARC_DB": str(database)},
        cwd=str(project),
    )
    async with stdio_client(parameters) as (read, write):
        async with ClientSession(read, write) as client:
            await client.initialize()
            handoff = await client.call_tool("arc_get_project_handoff", {})
            if handoff.is_error or "arc:event/" not in str(handoff):
                raise RuntimeError("Fresh MCP handoff lacked source-linked evidence")
            event = await client.call_tool("arc_get_event", {"event_id": event_id})
            if event.is_error or f"arc:event/{event_id}" not in str(event):
                raise RuntimeError("Fresh MCP session could not resolve the expected event")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--event", required=True)
    parser.add_argument("--query", required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--require-wifi-off", action="store_true")
    args = parser.parse_args()
    project, database = args.project.resolve(), args.db.resolve()
    report = {
        "date_manila": datetime.now(timezone(timedelta(hours=8))).isoformat(),
        "machine": platform.platform(),
        "project": project.name,
        "database": database.name,
        "wifi_power": None,
        "external_tcp_connected": None,
        "checks": {},
    }
    try:
        power = subprocess.run(
            ["networksetup", "-getairportpower", "en0"],
            capture_output=True, text=True, check=True, timeout=5,
        ).stdout.strip()
        report["wifi_power"] = power
        if args.require_wifi_off and not power.endswith(": Off"):
            raise RuntimeError("Wi-Fi is still on; physical offline trial did not start")
        try:
            with socket.create_connection(("1.1.1.1", 443), timeout=2):
                report["external_tcp_connected"] = True
        except OSError:
            report["external_tcp_connected"] = False
        if report["external_tcp_connected"]:
            raise RuntimeError("An external TCP connection succeeded")
        report["checks"]["external_network_unreachable"] = True

        started = perf_counter()
        search = run_cli(project, database, "search", args.query, "--semantic-only")
        rank = next((index for index, hit in enumerate(search["hits"], 1)
                     if hit["event_id"] == args.event and
                     hit["source_ref"] == f"arc:event/{args.event}"), None)
        if search["mode"] != "semantic" or rank is None:
            raise RuntimeError("Semantic search did not return the expected source")
        report["checks"]["semantic_search"] = {
            "mode": search["mode"], "source_ref": f"arc:event/{args.event}",
            "expected_event_rank": rank,
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        }

        started = perf_counter()
        chat = run_cli(project, database, "chat", args.query, "--timezone-offset", "480")
        if (chat["mode"] != "local_model_selection" or
                chat["retrieval_mode"] != "semantic" or
                not any(item["source_ref"] == f"arc:event/{args.event}"
                        for item in chat["citations"])):
            raise RuntimeError("Local chat did not cite the expected evidence")
        report["checks"]["cited_local_chat"] = {
            "mode": chat["mode"], "retrieval_mode": chat["retrieval_mode"],
            "citation_ids": [item["id"] for item in chat["citations"]],
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        }

        started = perf_counter()
        asyncio.run(check_mcp(project, database, args.event))
        report["checks"]["fresh_mcp_handoff_and_event"] = {
            "source_ref": f"arc:event/{args.event}",
            "elapsed_ms": round((perf_counter() - started) * 1000, 1),
        }
        report["status"] = "passed"
    except Exception as error:
        report["status"] = "failed"
        report["error"] = str(error)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
