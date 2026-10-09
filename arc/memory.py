"""Local semantic retrieval from selected evidence summaries."""

import json
import math
import re
import unicodedata
from dataclasses import asdict
from typing import Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import ProxyHandler, Request, build_opener

from arc.contracts import SearchHit
from arc.store import Store

DEFAULT_MODEL = "all-minilm"
DEFAULT_OLLAMA_URL = "http://127.0.0.1:11434/api/embed"


class EmbeddingUnavailable(RuntimeError):
    pass


class Embedder(Protocol):
    model: str

    def embed(self, text: str) -> list[float]: ...


class OllamaEmbedder:
    """Calls only the local Ollama endpoint; no cloud fallback."""

    def __init__(self, model: str = DEFAULT_MODEL, url: str = DEFAULT_OLLAMA_URL):
        parsed = urlparse(url)
        if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost"}:
            raise ValueError("Ollama URL must point to the local computer")
        self.model = model
        self.url = url
        self._opener = build_opener(ProxyHandler({}))

    def embed(self, text: str) -> list[float]:
        request = Request(
            self.url,
            data=json.dumps({"model": self.model, "input": text[:2000]}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with self._opener.open(request, timeout=20) as response:
                payload = json.load(response)
        except (URLError, HTTPError, TimeoutError, OSError) as error:
            raise EmbeddingUnavailable(
                f"Local Ollama embedding failed: {error}. Start Ollama and run 'ollama pull {self.model}'."
            ) from error
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or not vectors or not isinstance(vectors[0], list):
            raise EmbeddingUnavailable("Ollama returned no embedding vector")
        values = [float(value) for value in vectors[0]]
        if not values or not all(math.isfinite(value) for value in values):
            raise EmbeddingUnavailable("Ollama returned an invalid embedding vector")
        return values


def cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = math.sqrt(sum(value * value for value in left))
    norm_right = math.sqrt(sum(value * value for value in right))
    if norm_left == 0 or norm_right == 0:
        return -1.0
    return dot / (norm_left * norm_right)


def redact(text: str) -> str:
    """Remove common secrets from text explicitly submitted to memory."""
    text = re.sub(r"\bAKIA[0-9A-Z]{16}\b", "[REDACTED AWS KEY]", text)
    text = re.sub(r"\b(?:ghp_|github_pat_|sk-)[A-Za-z0-9_\-]{12,}\b",
                  "[REDACTED TOKEN]", text)
    text = re.sub(r"\b(password|token|api[_-]?key)\s*[:=]\s*[^\s,;]+",
                  r"\1=[REDACTED]", text, flags=re.IGNORECASE)
    return text[:2000]


def normalize_index_text(text: str) -> str:
    """Normalize the searchable copy without changing the evidence record."""
    return " ".join(unicodedata.normalize("NFKC", text).split())[:2000]


def _hit(event: dict, score: float) -> dict:
    return asdict(SearchHit(event["id"], event["kind"], event["summary"],
                            event["source_ref"], event["created_at"],
                            round(score, 6)))


class MemoryEngine:
    def __init__(self, store: Store, embedder: Embedder | None = None):
        self.store = store
        self.embedder = embedder or OllamaEmbedder()

    def index_pending(self, project_id: str) -> dict:
        events = self.store.pending_embeddings(project_id, self.embedder.model)
        count = 0
        for event in events:
            vector = self.embedder.embed(normalize_index_text(event["summary"]))
            self.store.put_vector(event["id"], self.embedder.model, vector)
            count += 1
        return {"indexed": count, "model": self.embedder.model}

    def search(self, project_id: str, query: str, limit: int = 5,
               allow_keyword_fallback: bool = True, kind: str | None = None,
               keyword_only: bool = False, hybrid: bool = False) -> dict:
        if not query.strip():
            raise ValueError("Search query must not be empty")
        if (keyword_only and (not allow_keyword_fallback or hybrid)) or (
            hybrid and not allow_keyword_fallback
        ):
            raise ValueError("Choose only one of keyword-only, semantic-only, or hybrid search")
        limit = min(max(limit, 1), 20)
        kind = kind.strip() if kind else None
        counts = self.store.index_counts(project_id, self.embedder.model, kind)

        def keyword_result(mode: str, reason: str | None = None) -> dict:
            events = self.store.keyword_search(project_id, query, limit, kind)
            result = {"mode": mode, "score_kind": "keyword_rank",
                      **counts,
                      "hits": [_hit(event, 1 / rank)
                               for rank, event in enumerate(events, start=1)]}
            if reason:
                result["reason"] = reason
            return result

        if keyword_only:
            return keyword_result("keyword")
        try:
            query_vector = self.embedder.embed(query)
        except EmbeddingUnavailable as error:
            if not allow_keyword_fallback:
                raise
            return keyword_result("keyword_fallback", str(error))
        ranked = []
        for event, vector in self.store.vectors(project_id, self.embedder.model, kind):
            similarity = cosine(query_vector, vector)
            if similarity >= 0:
                ranked.append((event, similarity))
        ranked.sort(key=lambda item: item[1], reverse=True)

        notice = ("No indexed records for this search. Run 'arc index' first."
                  if counts["indexed_records"] == 0 and counts["pending_records"] else None)
        if not ranked and counts["indexed_records"] == 0 and allow_keyword_fallback:
            return keyword_result("keyword_fallback", notice or "No records are indexed")

        if not hybrid:
            result = {"mode": "semantic", "model": self.embedder.model,
                      "score_kind": "cosine", **counts,
                      "hits": [_hit(event, score) for event, score in ranked[:limit]]}
            if notice:
                result["notice"] = notice
            return result

        # Reciprocal rank fusion makes exact FTS5 hits and paraphrase hits compete
        # without treating cosine similarity or bm25 as a probability.
        events_by_id: dict[str, dict] = {}
        fused: dict[str, float] = {}
        for rank, (event, _) in enumerate(ranked[:100], start=1):
            events_by_id[event["id"]] = event
            fused[event["id"]] = fused.get(event["id"], 0.0) + 1 / (60 + rank)
        exact = self.store.keyword_search(project_id, query, 100, kind)
        for rank, event in enumerate(exact, start=1):
            events_by_id[event["id"]] = event
            fused[event["id"]] = fused.get(event["id"], 0.0) + 1 / (60 + rank)
        ordered = sorted(fused, key=lambda event_id: (
            fused[event_id], events_by_id[event_id]["created_at"]), reverse=True)
        return {"mode": "hybrid", "model": self.embedder.model,
                "score_kind": "rrf", **counts,
                "hits": [_hit(events_by_id[event_id], fused[event_id])
                         for event_id in ordered[:limit]]}
