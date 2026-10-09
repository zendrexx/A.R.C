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
                            "Postgres database connection timed out during startup")
        service.record_note(sample_repo, "decision",
                            "Choose a green color palette for the dashboard")
        assert service.index_memory(sample_repo)["indexed"] == 2
        result = service.search_memory(sample_repo,
                                       "Why could the app not connect to its database?",
                                       allow_keyword_fallback=False)
        assert result["mode"] == "semantic"
        assert "database connection" in result["hits"][0]["summary"].lower()
    finally:
        service.close()
