"""Conservative, source-linked matching of explicitly recorded incidents."""

import re
import unicodedata

from arc.store import SEARCH_STOPWORDS

MIN_SEMANTIC_SIMILARITY = 0.55
GENERIC_ERROR_WORDS = frozenset({"error", "failed", "failure", "exception", "problem"})


def normalize_cause(value: str) -> str:
    return " ".join(unicodedata.normalize("NFKC", value).casefold().split())


def _tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return {token for token in re.findall(r"[\w]+", normalized, flags=re.UNICODE)
            if len(token) > 2 and token not in SEARCH_STOPWORDS
            and token not in GENERIC_ERROR_WORDS}


def _keyword_evidence(query: str, summary: str) -> bool:
    query_tokens = _tokens(query)
    summary_tokens = _tokens(summary)
    shared = query_tokens & summary_tokens
    return (len(shared) >= 2 and len(shared) / min(len(query_tokens), len(summary_tokens)) >= 0.4)


def select_incident_matches(hits: list[dict], mode: str,
                            by_error_event: dict[str, dict], query: str,
                            cause: str | None, limit: int) -> dict:
    """Keep plausible incidents and separate explicitly different root causes."""
    candidates = []
    different_causes = []
    weak_rejections = 0
    for hit in hits:
        incident = by_error_event.get(hit["event_id"])
        if not incident:
            continue
        if mode == "semantic":
            relevant = hit["score"] >= MIN_SEMANTIC_SIMILARITY
        else:
            relevant = _keyword_evidence(query, hit["summary"])
        if not relevant:
            weak_rejections += 1
            continue
        if cause is None:
            relation = "cause_not_supplied"
        elif incident["cause"] is None:
            relation = "cause_not_recorded"
        elif normalize_cause(cause) == normalize_cause(incident["cause"]):
            relation = "same_recorded_cause"
        else:
            relation = "different_recorded_cause"
        item = {"incident_id": incident["id"], "error": hit,
                "cause_relation": relation, "match_status": "candidate_not_confirmed"}
        target = different_causes if relation == "different_recorded_cause" else candidates
        if len(target) < limit:
            target.append(item)
    return {"candidates": candidates, "different_causes": different_causes,
            "weak_rejections": weak_rejections}
