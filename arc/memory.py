"""Local semantic retrieval from selected evidence summaries."""

import json
import math
import re
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


class MemoryEngine:
    def __init__(self, store: Store, embedder: Embedder | None = None):
        self.store = store
        self.embedder = embedder or OllamaEmbedder()

    def index_pending(self, project_id: str) -> dict:
        events = self.store.pending_embeddings(project_id, self.embedder.model)
        count = 0
        for event in events:
            vector = self.embedder.embed(event["summary"])
            self.store.put_vector(event["id"], self.embedder.model, vector)
            count += 1
        return {"indexed": count, "model": self.embedder.model}

    def search(self, project_id: str, query: str, limit: int = 5,
               allow_keyword_fallback: bool = True) -> dict:
        if not query.strip():
            raise ValueError("Search query must not be empty")
        limit = min(max(limit, 1), 20)
        try:
            query_vector = self.embedder.embed(query)
        except EmbeddingUnavailable as error:
            if not allow_keyword_fallback:
                raise
            events = self.store.keyword_search(project_id, query, limit)
            return {
                "mode": "keyword_fallback", "reason": str(error),
                "hits": [asdict(SearchHit(event["id"], event["kind"], event["summary"],
                                          event["source_ref"], event["created_at"], 0.0))
                         for event in events],
            }
        ranked = []
        for event, vector in self.store.vectors(project_id, self.embedder.model):
            similarity = cosine(query_vector, vector)
            if similarity >= 0:
                ranked.append(SearchHit(event["id"], event["kind"], event["summary"],
                                        event["source_ref"], event["created_at"],
                                        round(similarity, 4)))
        ranked.sort(key=lambda hit: hit.score, reverse=True)
        return {"mode": "semantic", "model": self.embedder.model,
                "hits": [asdict(hit) for hit in ranked[:limit]]}
