"""Optional real-model check; skips when the local Ollama model is unavailable."""

import pytest

from arc.memory import EmbeddingUnavailable, OllamaEmbedder
from arc.service import ArcService


@pytest.mark.integration
def test_local_model_finds_a_paraphrased_incident(sample_repo, tmp_path):
    embedder = OllamaEmbedder()
    try:
        embedder.embed("A.R.C. local model health check")
    except EmbeddingUnavailable as error:
        pytest.skip(str(error))
    service = ArcService(tmp_path / "arc.sqlite3", embedder)
    try:
        service.register_project(sample_repo)
        service.record_note(sample_repo, "error",
                            "SQLite migration failed because the users table did not exist")
        service.record_note(sample_repo, "decision",
                            "Choose a green color palette for the dashboard")
        assert service.index_memory(sample_repo)["indexed"] == 2
        query = "Why did the database upgrade break?"
        project_id = service.store.get_project(sample_repo)["id"]
        assert service.store.keyword_search(project_id, query, 5) == []
        result = service.search_memory(sample_repo,
                                       query,
                                       allow_keyword_fallback=False)
        assert result["mode"] == "semantic"
        assert "sqlite migration" in result["hits"][0]["summary"].lower()
    finally:
        service.close()
