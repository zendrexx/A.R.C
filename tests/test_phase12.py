"""Reliability gates for the integrated local extension workflow."""
import json
import os
import subprocess
from datetime import datetime, timezone

import pytest

from arc.chat import answer, calendar_bounds
from arc.git_evidence import snapshot
from arc.observer import control, poll, status
from arc.service import ArcService


@pytest.fixture
def service(sample_repo, tmp_path):
    instance = ArcService(tmp_path / 'phase12.sqlite3')
    instance.register_project(sample_repo)
    yield instance
    instance.close()


def commit(repo, message):
    subprocess.run(['git', '-C', str(repo), 'add', 'app.py'], check=True)
    subprocess.run(['git', '-C', str(repo), 'commit', '-qm', message], check=True)


def test_observer_deduplicates_restarts_and_recovers_external_commit(service, sample_repo):
    control(service, sample_repo, 'enable')
    (sample_repo / 'app.py').write_text('print("changed")\n')
    first = poll(service, sample_repo)
    assert len(first) == 1
    assert all(poll(service, sample_repo) == [] for _ in range(10))
    commit(sample_repo, 'change outside editor')
    recovered = poll(service, sample_repo)
    assert len(recovered) == 1
    assert recovered[0]['source'] == 'observer_commit'
    assert poll(service, sample_repo) == []


def test_recovered_commit_keeps_original_date_in_timeline(service, sample_repo):
    control(service, sample_repo, 'enable')
    (sample_repo / 'app.py').write_text('print("historical commit")\n')
    subprocess.run(['git', '-C', str(sample_repo), 'add', 'app.py'], check=True)
    environment = {**os.environ, 'GIT_AUTHOR_DATE':'2026-10-08T12:00:00+08:00',
                   'GIT_COMMITTER_DATE':'2026-10-08T12:00:00+08:00'}
    subprocess.run(['git', '-C', str(sample_repo), 'commit', '-qm', 'historical change'], env=environment, check=True)
    event = poll(service, sample_repo)[0]
    assert event['created_at'] == '2026-10-08T04:00:00+00:00'
    assert event['details']['observed_at']
    page = service.store.timeline(service._project(sample_repo)['id'],
        since='2026-10-08T00:00:00Z', until='2026-10-09T00:00:00Z')
    assert page['events'][0]['id'] == event['id']
    control(service, sample_repo, 'enable')
    assert poll(service, sample_repo) == []


def test_paused_activity_is_discarded_and_disable_stops_collection(service, sample_repo):
    with pytest.raises(ValueError, match='Enable observation explicitly'):
        control(service, sample_repo, 'resume')
    control(service, sample_repo, 'enable')
    control(service, sample_repo, 'pause')
    (sample_repo / 'app.py').write_text('print("private interval")\n')
    commit(sample_repo, 'paused commit')
    assert poll(service, sample_repo) == []
    control(service, sample_repo, 'resume')
    assert poll(service, sample_repo) == []
    control(service, sample_repo, 'disable')
    (sample_repo / 'app.py').write_text('print("disabled")\n')
    assert poll(service, sample_repo) == []
    assert not status(service, sample_repo)['enabled']
    control(service, sample_repo, 'enable')
    assert poll(service, sample_repo) == []


def test_sensitive_paths_do_not_trigger_observation(service, sample_repo):
    # Include a tracked sensitive path, not just an untracked one.
    (sample_repo / '.env').write_text('TOKEN=first\n')
    subprocess.run(['git', '-C', str(sample_repo), 'add', '.env'], check=True)
    subprocess.run(['git', '-C', str(sample_repo), 'commit', '-qm', 'setup'], check=True)
    control(service, sample_repo, 'enable')
    baseline = snapshot(sample_repo).fingerprint
    (sample_repo / '.env').write_text('TOKEN=second\n')
    (sample_repo / 'node_modules').mkdir()
    (sample_repo / 'node_modules' / 'cache.txt').write_text('generated')
    assert snapshot(sample_repo).fingerprint == baseline
    assert poll(service, sample_repo) == []
    assert service.store.events(service._project(sample_repo)['id']) == []


def test_chat_citations_are_real_and_claims_remain_unverified(service, sample_repo):
    task = service.add_task(sample_repo, 'login')
    event = service.record_note(sample_repo, 'claim', 'Login is complete', task['id'])
    result = answer(service, sample_repo, 'Where did we leave off?', keyword_only=True)
    assert result['citations'][0]['id'] == event['id']
    assert 'Unverified claim' in result['answer']
    assert service.project_state(sample_repo)['tasks'][0]['state'] == 'planned'
    assert service.get_event(sample_repo, result['citations'][0]['id'])['id'] == event['id']


def test_chat_requires_local_ollama(monkeypatch, service, sample_repo):
    from urllib.error import URLError
    from arc.memory import EmbeddingUnavailable
    service.record_note(sample_repo, 'note', 'offline fact')
    class Tags:
        def __init__(self, payload=None, error=None):
            self.payload = payload
            self.error = error
        def open(self, *_args, **_kwargs):
            if self.error:
                raise self.error
            payload = self.payload
            class Response:
                def __enter__(self): return self
                def __exit__(self, *_): pass
                def read(self): return json.dumps(payload).encode()
            return Response()
    monkeypatch.setattr('arc.chat.build_opener', lambda *_: Tags(error=URLError('refused')))
    with pytest.raises(EmbeddingUnavailable, match='requires Ollama'):
        answer(service, sample_repo, 'Where did we leave off?')
    monkeypatch.setattr('arc.chat.build_opener', lambda *_: Tags({'models': []}))
    with pytest.raises(EmbeddingUnavailable, match='ollama pull qwen3'):
        answer(service, sample_repo, 'Where did we leave off?')
    monkeypatch.setattr('arc.chat.build_opener',
                        lambda *_: Tags({'models': [{'name': 'qwen3:1.7b'}]}))
    result = answer(service, sample_repo, 'Where did we leave off?')
    assert result['citations'][0]['summary'] == 'offline fact'
    assert result['notice']


def test_model_cannot_introduce_unknown_citations(service, sample_repo):
    event = service.record_note(sample_repo, 'note', 'Started login work')
    class InvalidModel:
        def select(self, *_):
            raise ValueError('Model cited evidence outside the retrieved set')
    result = answer(service, sample_repo, 'Where did we leave off?', chat=InvalidModel())
    assert result['mode'] == 'evidence'
    assert result['citations'][0]['id'] == event['id']
    assert result['notice']


def test_model_lease_serializes_processes_and_recovers(service, sample_repo):
    from arc.memory import EmbeddingUnavailable
    from arc.model_gate import model_slot
    other = ArcService(service.store.path)
    try:
        with model_slot(service.store):
            with pytest.raises(EmbeddingUnavailable, match='active'):
                with model_slot(other.store):
                    pass
        with model_slot(other.store):
            pass
        other.store.connection.execute('INSERT INTO model_lease VALUES (1, ?, 0)', ('expired',))
        other.store.connection.commit()
        with model_slot(service.store):
            pass
    finally:
        other.close()


def test_durable_index_queue_retries_without_duplicates(service, sample_repo):
    from arc.memory import EmbeddingUnavailable
    class Embedder:
        model = 'fixture'
        offline = True
        def embed(self, _):
            if self.offline:
                raise EmbeddingUnavailable('offline')
            return [1.0, 0.0]
    embedder = Embedder()
    service.memory.embedder = embedder
    for i in range(5):
        service.record_note(sample_repo, 'note', f'queue event {i}')
    project_id = service._project(sample_repo)['id']
    with pytest.raises(EmbeddingUnavailable):
        service.memory.index_pending(project_id, limit=2)
    assert service.store.index_counts(project_id, 'fixture')['pending_records'] == 5
    embedder.offline = False
    assert service.memory.index_pending(project_id, limit=2)['indexed'] == 2
    assert service.memory.index_pending(project_id, limit=2)['indexed'] == 2
    assert service.memory.index_pending(project_id, limit=2)['indexed'] == 1
    assert service.memory.index_pending(project_id, limit=2)['indexed'] == 0


def test_chat_and_timeline_never_mix_project_records(service, sample_repo, tmp_path):
    other = tmp_path / 'other'
    other.mkdir()
    project = service.store.register_project(other)
    private = service.store.add_event(project['id'], 'note', 'private project fact', 'explicit', 'auto')
    event = service.record_note(sample_repo, 'note', 'selected project fact')
    result = answer(service, sample_repo, 'Summarize the timeline', keyword_only=True)
    assert [e['id'] for e in result['citations']] == [event['id']]
    assert private['summary'] not in result['answer']
    with pytest.raises(ValueError, match='not found'):
        service.get_event(sample_repo, private['id'])


def test_missing_rationale_is_not_invented(service, sample_repo):
    service.capture_git(sample_repo)
    result = answer(service, sample_repo, 'Why did we implement login?', keyword_only=True)
    assert result['answer'] == 'No recorded rationale supports this answer.'
    assert result['citations'] == []


def test_local_calendar_and_timeline_pagination(service, sample_repo):
    now = datetime(2026, 10, 9, 1, tzinfo=timezone.utc)
    start, end = calendar_bounds('What happened yesterday?', 480, now)
    assert start == '2026-10-07T16:00:00+00:00'
    assert end == '2026-10-08T16:00:00+00:00'
    for number in range(25):
        service.record_note(sample_repo, 'note', f'Event {number}')
    first = answer(service, sample_repo, 'Summarize our timeline', keyword_only=True)
    service.record_note(sample_repo, 'note', 'Arrived while browsing history')
    second = answer(service, sample_repo, 'Summarize our timeline', keyword_only=True,
                    offset=first['next_offset'], snapshot_rowid=first['snapshot_rowid'])
    assert len(first['citations']) == len(second['citations']) == 12
    assert not {e['id'] for e in first['citations']} & {e['id'] for e in second['citations']}
    assert second['next_offset'] == 24


def test_latest_change_after_local_midnight(service, sample_repo, monkeypatch):
    import arc.chat as module
    now = datetime(2026, 10, 9, 17, tzinfo=timezone.utc)
    start, end = calendar_bounds('most recent change 12:30am onwards', 480, now)
    assert start == '2026-10-09T16:30:00+00:00'
    monkeypatch.setattr(module, 'calendar_bounds', lambda *_: (start, end))
    project = service._project(sample_repo)
    for minute in (20, 38):
        event = service.store.add_event(project['id'], 'git', f'Changed docs at {minute}',
            'git', f'test:{minute}', created_at=f'2026-10-09T16:{minute}:00+00:00')
    service.record_note(sample_repo, 'note', 'Unrelated newer note')
    result = answer(service, sample_repo, 'most recent change 12:30am onwards', 480, keyword_only=True)
    assert [e['id'] for e in result['citations']] == [event['id']]
    assert result['next_offset'] is None


def test_generated_answer_uses_recorded_citations(service, sample_repo):
    event = service.record_note(sample_repo, 'note', 'Started login work')
    class Model:
        def respond(self, question, events):
            return 'You started login work.', [event['id']]
    result = answer(service, sample_repo, 'Where did we leave off?', chat=Model())
    assert result['answer_intro'] == 'You started login work.'
    assert result['mode'] == 'local_model_answer'
    assert result['citations'][0]['id'] == event['id']


@pytest.mark.parametrize('word', ['oldest', 'earliest', 'first'])
def test_oldest_change_returns_one_earliest_git_record(service, sample_repo, word):
    project = service._project(sample_repo)
    # Insert out of timestamp order, with more history than a chat page.
    for number in range(15, 0, -1):
        event = service.store.add_event(project['id'], 'git', f'Change {number}', 'git',
            f'change:{number}', created_at=f'2026-10-{number:02d}T16:00:00+00:00')
    service.store.add_event(project['id'], 'note', 'Older non-Git note', 'explicit', 'note',
        created_at='2026-09-01T00:00:00+00:00')
    result = answer(service, sample_repo, f'what time was my {word} change', 480,
        keyword_only=True, offset=10)
    assert [e['id'] for e in result['citations']] == [event['id']]
    assert result['since'] is None
    assert result['next_offset'] is None
    latest = answer(service, sample_repo, 'most recent change', keyword_only=True)
    assert latest['citations'][0]['summary'] == 'Change 15'


def test_ollama_request_is_local_bounded_and_unloads(monkeypatch):
    from arc.chat import OllamaChat
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return json.dumps({'message': {'content': '{"event_ids":["real"]}'}}).encode()
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == 'http://127.0.0.1:11434/api/chat'
            body = json.loads(request.data)
            assert body['keep_alive'] == 0
            assert body['options']['num_ctx'] == 4096
            assert timeout == 45
            return Response()
    monkeypatch.setattr('arc.chat.build_opener', lambda *_: Opener())
    model = OllamaChat()
    assert model.select('question', [{'id':'real', 'kind':'note', 'summary':'fact', 'created_at':'today'}]) == ['real']
    with pytest.raises(ValueError, match='outside'):
        model.select('question', [{'id':'other', 'kind':'note', 'summary':'fact', 'created_at':'today'}])
