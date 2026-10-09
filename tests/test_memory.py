from arc.memory import EmbeddingUnavailable, MemoryEngine, normalize_index_text, redact
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
        result = memory.search(project["id"], "connection failure",
                               allow_keyword_fallback=False)
        assert result["mode"] == "semantic"
        assert result["hits"][0]["summary"] == "Database connection timed out"
        assert result["hits"][0]["source_ref"] == "evidence:1"

        hybrid = memory.search(project["id"], "Database connection", hybrid=True)
        assert hybrid["mode"] == "hybrid"
        assert hybrid["score_kind"] == "rrf"
        assert hybrid["hits"][0]["source_ref"] == "evidence:1"
        assert len({hit["event_id"] for hit in hybrid["hits"]}) == len(hybrid["hits"])

        fallback = MemoryEngine(store, OfflineEmbedder()).search(project["id"], "Database")
        assert fallback["mode"] == "keyword_fallback"
        assert fallback["hits"][0]["summary"] == "Database connection timed out"
    finally:
        store.close()


def test_search_filters_by_project_and_kind_without_requiring_ollama(tmp_path):
    store = Store(tmp_path / "memory.sqlite3")
    try:
        project = store.register_project(tmp_path)
        other_folder = tmp_path / "other"
        other_folder.mkdir()
        other = store.register_project(other_folder)
        expected = store.add_event(project["id"], "error", "Database request failed",
                                   "explicit", "auto")
        store.add_event(project["id"], "decision", "Database migration approved",
                        "explicit", "auto")
        store.add_event(other["id"], "error", "Database project secret",
                        "explicit", "auto")
        memory = MemoryEngine(store, FakeEmbedder())
        memory.index_pending(project["id"])
        memory.index_pending(other["id"])

        hybrid = memory.search(project["id"], "Database", kind="error", hybrid=True)
        assert [hit["event_id"] for hit in hybrid["hits"]] == [expected["id"]]
        assert hybrid["indexed_records"] == 1
        keyword = MemoryEngine(store, OfflineEmbedder()).search(
            project["id"], "Database", kind="error", keyword_only=True)
        assert keyword["mode"] == "keyword"
        assert [hit["event_id"] for hit in keyword["hits"]] == [expected["id"]]
    finally:
        store.close()


def test_unindexed_search_explains_empty_semantic_results(tmp_path):
    store = Store(tmp_path / "memory.sqlite3")
    try:
        project = store.register_project(tmp_path)
        store.add_event(project["id"], "error", "Database migration failed",
                        "explicit", "auto")
        memory = MemoryEngine(store, FakeEmbedder())
        semantic = memory.search(project["id"], "Database", allow_keyword_fallback=False)
        assert semantic["hits"] == []
        assert semantic["pending_records"] == 1
        assert "arc index" in semantic["notice"]
        fallback = memory.search(project["id"], "Database")
        assert fallback["mode"] == "keyword_fallback"
        assert len(fallback["hits"]) == 1
    finally:
        store.close()


def test_index_text_normalization_preserves_original_evidence(tmp_path):
    class RecordingEmbedder:
        model = "recording"
        texts = []

        def embed(self, value: str) -> list[float]:
            self.texts.append(value)
            return [1.0, 0.0]

    store = Store(tmp_path / "memory.sqlite3")
    try:
        project = store.register_project(tmp_path)
        event = store.add_event(project["id"], "error", "  Database \n  connection   failed  ",
                                "explicit", "auto")
        embedder = RecordingEmbedder()
        MemoryEngine(store, embedder).index_pending(project["id"])
        assert embedder.texts == ["Database connection failed"]
        assert store.get_event(event["id"])["summary"] == "  Database \n  connection   failed  "
        assert normalize_index_text("ＡＲＣ  memory") == "ARC memory"
    finally:
        store.close()


def test_common_secret_patterns_are_redacted():
    text = "password=hunter2 token: ghp_abcdefghijklmnop AKIAABCDEFGHIJKLMNOP"
    cleaned = redact(text)
    assert "hunter2" not in cleaned
    assert "ghp_" not in cleaned
    assert "AKIA" not in cleaned
