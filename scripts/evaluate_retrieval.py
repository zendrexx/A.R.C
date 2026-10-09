"""Compare local semantic, keyword, and hybrid search on fixed synthetic cases."""

import json
import statistics
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from arc.memory import EmbeddingUnavailable, MemoryEngine
from arc.store import Store

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "retrieval_cases.json"


def _rank(hits: list[dict], expected_id: str) -> int | None:
    return next((rank for rank, hit in enumerate(hits, start=1)
                 if hit["event_id"] == expected_id), None)


def main() -> int:
    fixture = json.loads(FIXTURES.read_text())
    with TemporaryDirectory(prefix="arc-retrieval-eval-") as directory:
        store = Store(Path(directory) / "memory.sqlite3")
        try:
            project_id = store.register_project(Path(directory))["id"]
            ids = {item["key"]: store.add_event(
                project_id, item["kind"], item["summary"], "synthetic_fixture", "auto"
            )["id"] for item in fixture["incidents"]}
            keys_by_id = {event_id: key for key, event_id in ids.items()}
            memory = MemoryEngine(store)
            memory.index_pending(project_id)
            results = {mode: [] for mode in ("keyword", "semantic", "hybrid")}
            cases = []
            for case in fixture["queries"]:
                row = {"query": case["query"], "expected": case["key"]}
                for mode in results:
                    started = perf_counter()
                    if mode == "keyword":
                        response = memory.search(project_id, case["query"], keyword_only=True)
                    elif mode == "semantic":
                        response = memory.search(project_id, case["query"],
                                                 allow_keyword_fallback=False)
                    else:
                        response = memory.search(project_id, case["query"], hybrid=True)
                    elapsed_ms = round((perf_counter() - started) * 1000, 2)
                    rank = _rank(response["hits"], ids[case["key"]])
                    top_id = response["hits"][0]["event_id"] if response["hits"] else None
                    row[mode] = {"rank": rank,
                                 "top_hit": keys_by_id.get(top_id),
                                 "latency_ms": elapsed_ms}
                    results[mode].append(row[mode])
                cases.append(row)

            metrics = {}
            for mode, rows in results.items():
                count = len(rows)
                metrics[mode] = {
                    "top1": sum(row["rank"] == 1 for row in rows),
                    "recall_at_3": sum(row["rank"] is not None and row["rank"] <= 3
                                       for row in rows),
                    "mrr": round(sum(1 / row["rank"] if row["rank"] else 0
                                     for row in rows) / count, 3),
                    "median_latency_ms": round(statistics.median(
                        row["latency_ms"] for row in rows), 2),
                }
            unrelated = memory.search(project_id, fixture["unrelated_query"],
                                      allow_keyword_fallback=False)
            unrelated_top = unrelated["hits"][0] if unrelated["hits"] else None
            print(json.dumps({
                "model": memory.embedder.model,
                "records": len(ids), "queries": len(cases),
                "metrics": metrics, "cases": cases,
                "unrelated_query_top_hit": (
                    {"key": keys_by_id[unrelated_top["event_id"]],
                     "cosine": unrelated_top["score"]}
                    if unrelated_top else None
                ),
            }, indent=2))
            return 0
        except EmbeddingUnavailable as error:
            print(f"A.R.C. retrieval evaluation needs local Ollama: {error}", file=sys.stderr)
            return 2
        finally:
            store.close()


if __name__ == "__main__":
    raise SystemExit(main())
