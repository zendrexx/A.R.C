"""Manual model controls share the configured models and existing SQLite lease."""
import json
from arc.cli import main
from arc.chat import OllamaChat
from arc.memory import OllamaEmbedder


def test_model_preferences_reach_python(monkeypatch):
    monkeypatch.setenv('ARC_EMBEDDING_MODEL', 'custom-embed')
    monkeypatch.setenv('ARC_CHAT_MODEL', 'custom-chat:small')
    assert OllamaEmbedder().model == 'custom-embed'
    assert OllamaChat().model == 'custom-chat:small'


def test_activation_unloads_other_selected_model_first(monkeypatch, sample_repo, tmp_path, capsys):
    monkeypatch.setenv('ARC_EMBEDDING_MODEL', 'custom-embed')
    monkeypatch.setenv('ARC_CHAT_MODEL', 'custom-chat:small')
    calls = []
    class Response:
        def __init__(self, payload): self.payload = payload
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return json.dumps(self.payload).encode()
    class Opener:
        def open(self, request, timeout):
            if isinstance(request, str):
                assert request == 'http://127.0.0.1:11434/api/ps'
                return Response({'models': [{'name': 'custom-embed:latest'}]})
            calls.append((request.full_url, json.loads(request.data)))
            return Response({})
    monkeypatch.setattr('urllib.request.build_opener', lambda *_: Opener())
    result = main(['--project', str(sample_repo), '--db', str(tmp_path/'models.sqlite3'),
                   'model', 'load', '--role', 'chat'])
    assert result == 0
    assert calls[0][1]['model'] == 'custom-embed'
    assert calls[0][1]['keep_alive'] == 0
    assert calls[1][1]['model'] == 'custom-chat:small'
    assert calls[1][1]['keep_alive'] == '30s'
    assert json.loads(capsys.readouterr().out)['operation'] == 'load'
