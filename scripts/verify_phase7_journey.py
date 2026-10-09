"""Repeat the real dashboard + local search + checkpoint read path without writes."""

import argparse
import json
from pathlib import Path
from threading import Thread
from time import perf_counter
from urllib.parse import urlencode
from urllib.request import urlopen

from arc.dashboard import create_dashboard_server


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", type=Path, required=True)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--task", required=True, help="expected unfinished task ID")
    parser.add_argument("--event", required=True, help="expected source event ID")
    parser.add_argument("--query", required=True, help="semantic query for the event")
    parser.add_argument("--rounds", type=int, default=2)
    args = parser.parse_args()
    if args.rounds < 2 or args.rounds > 10:
        parser.error("--rounds must be between 2 and 10")

    server = create_dashboard_server(args.db, port=0)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"

    def get(route: str, **parameters):
        url = base + route + "?" + urlencode({"project": str(args.project.resolve()),
                                               **parameters})
        with urlopen(url, timeout=30) as response:
            return json.load(response)

    rounds = []
    try:
        for number in range(1, args.rounds + 1):
            started = perf_counter()
            overview = get("/api/overview")
            suggested = overview["handoff"]["suggested_next_task"]
            if not suggested or suggested["id"] != args.task:
                raise RuntimeError(f"Round {number}: expected unfinished task was not suggested")
            review = get("/api/task", id=args.task)
            if review["task"]["id"] != args.task:
                raise RuntimeError(f"Round {number}: task review mismatch")
            search = get("/api/search", q=args.query, mode="semantic")
            if search["mode"] != "semantic":
                raise RuntimeError(f"Round {number}: semantic search fell back to {search['mode']}")
            rank = next((index for index, hit in enumerate(search["hits"], 1)
                         if hit["event_id"] == args.event), None)
            if rank is None:
                raise RuntimeError(f"Round {number}: expected event was absent from search hits")
            event = get("/api/event", id=args.event)
            if event["source_ref"] != f"arc:event/{args.event}":
                raise RuntimeError(f"Round {number}: source reference did not resolve")
            checkpoints = get("/api/checkpoints")
            if not checkpoints:
                raise RuntimeError(f"Round {number}: no checkpoint could be inspected")
            rounds.append({"round": number, "task_state": review["task"]["state"],
                           "expected_event_rank": rank, "source_ref": event["source_ref"],
                           "checkpoint_id": checkpoints[0]["id"],
                           "checkpoint_stale": checkpoints[0]["stale"],
                           "elapsed_ms": round((perf_counter() - started) * 1000, 1)})
        print(json.dumps({"status": "passed", "database": str(args.db.resolve()),
                          "project": str(args.project.resolve()),
                          "rounds": rounds,
                          "network_scope": "Dashboard and Ollama use loopback; this script does not disable Wi-Fi or prove physical disconnection."},
                         indent=2))
        return 0
    except Exception as error:
        print(json.dumps({"status": "failed", "error": str(error), "completed_rounds": rounds},
                         indent=2))
        return 1
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


if __name__ == "__main__":
    raise SystemExit(main())
