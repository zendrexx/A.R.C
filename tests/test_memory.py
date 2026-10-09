from arc.memory import EmbeddingUnavailable, MemoryEngine, redact
from arc.store import Store


class FakeEmbedder:
    model = "fake-local"

    def embed(self, text: str) -> list[float]:
        if "database" in text.lower() or "connection" in text.lower():
            return [1.0, 0.0]
        return [0.0, 1.0]


class OfflineEmbedder:
    model = "unavailable"

    def embed(self, text: str) -> list[float]:
        raise EmbeddingUnavailable("Ollama is not running")


def test_semantic_retrieval_and_keyword_fallback(tmp_path):
    store = Store(tmp_path / "memory.sqlite3")
    try:
        project = store.register_project(tmp_path)
        store.add_event(project["id"], "error", "Database connection timed out", "explicit", "evidence:1")
        store.add_event(project["id"], "decision", "Use a green theme", "explicit", "evidence:2")
        memory = MemoryEngine(store, FakeEmbedder())
        assert memory.index_pending(project["id"])["indexed"] == 2
        result = memory.search(project["id"], "connection failure")
        assert result["mode"] == "semantic"
        assert result["hits"][0]["summary"] == "Database connection timed out"
        assert result["hits"][0]["source_ref"] == "evidence:1"

        fallback = MemoryEngine(store, OfflineEmbedder()).search(project["id"], "Database")
        assert fallback["mode"] == "keyword_fallback"
        assert fallback["hits"][0]["summary"] == "Database connection timed out"
    finally:
        store.close()


def test_common_secret_patterns_are_redacted():
    text = "password=hunter2 token: ghp_abcdefghijklmnop AKIAABCDEFGHIJKLMNOP"
    cleaned = redact(text)
    assert "hunter2" not in cleaned
    assert "ghp_" not in cleaned
    assert "AKIA" not in cleaned
