"""Measure conservative incident retrieval on a labelled local-only fixture."""

import json
import statistics
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter

from arc.memory import EmbeddingUnavailable
from arc.service import ArcService

FIXTURE = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "phase7_incidents.json"


def main() -> int:
    cases = json.loads(FIXTURE.read_text())
    with TemporaryDirectory(prefix="arc-phase7-incidents-") as directory:
        root = Path(directory)
        project = root / "project"
        project.mkdir()
        subprocess.run(["git", "init", "-q", str(project)], check=True)
        service = ArcService(root / "evaluation.sqlite3")
        try:
            service.register_project(project)
            ids = {}
            error_ids = {}
            for item in cases["incidents"]:
                event = service.record_note(project, "error", item["error"])
                incident = service.open_incident(project, event["id"], item["cause"])
                ids[item["key"]] = incident["id"]
                error_ids[item["key"]] = event["id"]
            indexed = service.index_memory(project)
            if indexed["indexed"] < len(cases["incidents"]):
                raise RuntimeError("Some incident events were not indexed")

            positives = []
            negatives = []
            latencies = []
            raw_positives = []
            raw_negatives = []
            for item in cases["positive_queries"]:
                started = perf_counter()
                result = service.search_incidents(project, item["query"])
                latencies.append((perf_counter() - started) * 1000)
                candidates = result["candidates"]
                assert result["mode"] == "semantic", "Evaluation requires local semantic search"
                rank = next((index for index, candidate in enumerate(candidates, 1)
                             if candidate["incident_id"] == ids[item["key"]]), None)
                positives.append({"key": item["key"], "rank": rank,
                                  "candidate_count": len(candidates),
                                  "top_match": next((key for key, value in ids.items()
                                                     if candidates and value == candidates[0]["incident_id"]), None),
                                  "weak_rejections": result["weak_rejections"]})
                raw = service.search_memory(project, item["query"], limit=20,
                                            kind="error", allow_keyword_fallback=False)
                raw_positives.append({"expected_id": error_ids[item["key"]],
                                      "hits": raw["hits"]})
            for query in cases["negative_queries"]:
                started = perf_counter()
                result = service.search_incidents(project, query)
                latencies.append((perf_counter() - started) * 1000)
                assert result["mode"] == "semantic", "Evaluation requires local semantic search"
                negatives.append({"query": query, "candidate_count": len(result["candidates"]),
                                  "top_candidate": next((key for key, value in ids.items()
                                                         if result["candidates"] and value == result["candidates"][0]["incident_id"]), None)})
                raw = service.search_memory(project, query, limit=20,
                                            kind="error", allow_keyword_fallback=False)
                raw_negatives.append(raw["hits"])

            threshold_sweep = []
            for cutoff in (0.40, 0.45, 0.50, 0.55, 0.60):
                positive_expected = sum(any(hit["event_id"] == row["expected_id"]
                                            and hit["score"] >= cutoff
                                            for hit in row["hits"][:5])
                                        for row in raw_positives)
                negative_any = sum(any(hit["score"] >= cutoff for hit in hits[:5])
                                   for hits in raw_negatives)
                threshold_sweep.append({"cutoff": cutoff,
                                        "expected_in_top5": positive_expected,
                                        "negative_queries_with_candidate": negative_any})

            print(json.dumps({
                "fixture": str(FIXTURE.relative_to(FIXTURE.parents[1])),
                "fixture_type": "synthetic labelled development errors",
                "model": service.memory.embedder.model,
                "threshold": result["semantic_minimum"],
                "records": len(ids),
                "positive_queries": len(positives),
                "negative_queries": len(negatives),
                "top1_correct": sum(row["rank"] == 1 for row in positives),
                "expected_in_candidates": sum(row["rank"] is not None for row in positives),
                "negative_queries_with_any_candidate": sum(row["candidate_count"] > 0 for row in negatives),
                "median_query_latency_ms": round(statistics.median(latencies), 1),
                "positives": positives,
                "negatives": negatives,
                "threshold_sweep_diagnostic_only": threshold_sweep,
                "interpretation": "Small synthetic fixture; candidate status is not a confirmed diagnosis.",
            }, indent=2))
            return 0
        except (EmbeddingUnavailable, RuntimeError) as error:
            print(f"A.R.C. incident evaluation could not run: {error}", file=sys.stderr)
            return 2
        finally:
            service.close()


if __name__ == "__main__":
    raise SystemExit(main())
