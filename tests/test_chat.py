"""Phase 10 questions must use bounded, project-scoped evidence and honest labels."""

import json
from datetime import datetime, timezone

import pytest

from arc.chat import OllamaChat, answer
from arc.service import ArcService


@pytest.fixture
def service(sample_repo, tmp_path):
    instance = ArcService(tmp_path / 'chat.sqlite3')
    instance.register_project(sample_repo)
    yield instance
    instance.close()


def recorded(service, repo, kind, summary, timestamp):
    project = service._project(repo)
    return service.store.add_event(project['id'], kind, summary, 'explicit', 'auto',
                                   created_at=timestamp)


def test_local_today_yesterday_and_inclusive_date_range(service, sample_repo):
    before = recorded(service, sample_repo, 'note', 'Before local midnight',
                      '2026-10-08T15:59:00+00:00')
    today = recorded(service, sample_repo, 'note', 'At local midnight',
                     '2026-10-08T16:00:00+00:00')
    next_day = recorded(service, sample_repo, 'note', 'Next local midnight',
                        '2026-10-09T16:00:00+00:00')
    now = datetime(2026, 10, 9, 3, tzinfo=timezone.utc)
    current = answer(service, sample_repo, 'What happened today?', 480,
                     keyword_only=True, now=now)
    assert [item['id'] for item in current['citations']] == [today['id']]
    assert 'Today (2026-10-09)' in current['answer']
    assert '2026-10-09 00:00 +0800' in current['answer']
    assert current['day_counts']['days'] == [{'date': '2026-10-09', 'event_count': 1}]
    previous = answer(service, sample_repo, 'What changed yesterday?', 480,
                      keyword_only=True, now=now)
    assert [item['id'] for item in previous['citations']] == [before['id']]
    ranged = answer(service, sample_repo, 'Summarize 2026-10-08 through 2026-10-09',
                    480, keyword_only=True)
    assert {item['id'] for item in ranged['citations']} == {before['id'], today['id']}
    assert next_day['id'] not in ranged['answer']
    with pytest.raises(ValueError, match='valid dates'):
        answer(service, sample_repo, 'What happened 2026-13-01?', 480,
               keyword_only=True)


def test_task_answer_shows_state_without_claiming_completion(service, sample_repo):
    task = service.add_task(sample_repo, 'Login workflow')
    empty = answer(service, sample_repo, 'Status of Login workflow?', keyword_only=True)
    assert task['id'] in empty['answer'] and 'planned' in empty['answer']
    assert empty['citations'] == []
    claim = service.record_note(sample_repo, 'claim', 'Login workflow is finished', task['id'])
    result = answer(service, sample_repo, f'What is the status of task {task["id"]}?',
                    keyword_only=True)
    assert claim['id'] == result['citations'][0]['id']
    assert 'Unverified claim' in result['answer']
    assert 'planned' in result['answer']
    assert 'completed_confirmed' not in result['answer']


def test_fix_question_keeps_reported_resolution_separate_from_tests(service, sample_repo):
    error = service.record_note(sample_repo, 'error', 'Migration failed: missing table')
    incident = service.open_incident(sample_repo, error['id'], 'missing table')
    resolution = service.resolve_incident(sample_repo, incident['id'],
                                          'Created the table before migration')
    result = answer(service, sample_repo, 'What errors did we fix?', keyword_only=True)
    refs = {item['source_ref'] for item in result['citations']}
    assert error['source_ref'] in refs
    assert resolution['resolution']['source_ref'] in refs
    assert 'Reported resolution; fix not independently verified' in result['answer']
    assert 'No configured test is linked' in result['answer']
    # An unrelated passing test must not be presented as a check of this fix.
    recorded(service, sample_repo, 'test', 'Test passed: unrelated',
             '2026-10-10T00:00:00+00:00')
    repeated = answer(service, sample_repo, 'What errors did we fix?', keyword_only=True)
    assert 'No configured test is linked' in repeated['answer']


def test_error_question_without_resolution_does_not_infer_fix(service, sample_repo):
    error = service.record_note(sample_repo, 'error', 'Build failed')
    result = answer(service, sample_repo, 'Which errors did we fix?', keyword_only=True)
    assert [item['id'] for item in result['citations']] == [error['id']]
    assert 'No reported resolution was recorded' in result['answer']


def test_long_timeline_has_local_day_counts_and_stable_continuation(service, sample_repo):
    for index in range(30):
        recorded(service, sample_repo, 'note', f'Long history {index}',
                 f'2026-10-{index // 10 + 1:02d}T12:{index % 10:02d}:00+00:00')
    first = answer(service, sample_repo, 'Summarize our development timeline',
                   keyword_only=True, offset_minutes=480)
    assert first['total_events'] == 30
    assert len(first['citations']) == 12
    assert first['day_counts']['days'] == [
        {'date': '2026-10-03', 'event_count': 10},
        {'date': '2026-10-02', 'event_count': 10},
        {'date': '2026-10-01', 'event_count': 10},
    ]
    recorded(service, sample_repo, 'note', 'New event after first page',
             '2026-10-04T12:00:00+00:00')
    second = answer(service, sample_repo, 'Summarize our development timeline',
                    keyword_only=True, offset_minutes=480,
                    offset=first['next_offset'], snapshot_rowid=first['snapshot_rowid'])
    assert second['total_events'] == 30
    assert len(second['citations']) == 12
    assert not {item['id'] for item in first['citations']} & {
        item['id'] for item in second['citations']}
    assert 'More history is available' in second['answer']


def test_timeline_groups_noisy_observer_events_but_keeps_decisions(service, sample_repo):
    project = service._project(sample_repo)
    for index in range(20):
        service.store.add_event(project['id'], 'git', f'Observed paths {index}',
                                'observer', 'auto',
                                created_at=f'2026-10-01T12:{index:02d}:00+00:00')
    decision = recorded(service, sample_repo, 'decision', 'Keep the database local',
                        '2026-10-01T13:00:00+00:00')
    result = answer(service, sample_repo, 'Summarize our timeline',
                    keyword_only=True, offset_minutes=480)
    assert result['total_events'] == 21
    assert result['total_entries'] == 2
    assert len(result['citations']) == 2
    assert decision['id'] in {item['id'] for item in result['citations']}
    assert 'latest example of 20 observer Git events' in result['answer']
    assert len(service.store.timeline(project['id'], 30)['events']) == 21


def test_timeline_summary_includes_earlier_source_linked_milestone(service, sample_repo):
    project = service._project(sample_repo)
    decision = recorded(service, sample_repo, 'decision', 'Keep the database local',
                        '2026-10-01T12:00:00+00:00')
    for index in range(18):
        service.store.add_event(project['id'], 'git', f'Commit {index}',
                                'observer_commit', 'auto',
                                created_at=f'2026-10-02T12:{index:02d}:00+00:00')
    result = answer(service, sample_repo, 'Summarize our development timeline',
                    keyword_only=True, offset_minutes=480)
    assert result['next_offset'] == 12
    assert decision['id'] in {item['id'] for item in result['citations']}
    assert 'Selected earlier milestones' in result['answer']
    assert decision['source_ref'] in result['answer']


def test_why_question_rejects_unrelated_decision(service, sample_repo):
    service.record_note(sample_repo, 'decision', 'Use SQLite for local storage')
    result = answer(service, sample_repo, 'Why did we implement login?',
                    keyword_only=True)
    assert result['answer'] == 'No recorded rationale supports this answer.'
    assert result['citations'] == []


def test_model_selecting_nothing_does_not_erase_recorded_rationale(service, sample_repo):
    class Embedder:
        model = 'test'
        def embed(self, _text): return [1.0, 0.0]
    class EmptyModel:
        def select(self, _question, _events): return []
    service.memory.embedder = Embedder()
    service.record_note(sample_repo, 'decision', 'Use a login token because sessions expire')
    service.index_memory(sample_repo)
    result = answer(service, sample_repo, 'Why did we implement login?',
                    chat=EmptyModel())
    assert result['citations'] == []
    assert 'selected no relevant evidence' in result['answer']
    assert 'No recorded rationale' not in result['answer']


def test_large_history_never_enters_one_model_prompt(monkeypatch):
    captured = {}
    class Response:
        def __enter__(self): return self
        def __exit__(self, *_): pass
        def read(self): return b'{"message":{"content":"{\\"event_ids\\":[\\"event-0\\"]}"}}'
    class Opener:
        def open(self, request, timeout):
            captured.update(json.loads(request.data))
            assert timeout == 45
            return Response()
    monkeypatch.setattr('arc.chat.build_opener', lambda *_: Opener())
    events = [{'id': f'event-{index}', 'kind': 'note',
               'summary': 'Long recorded summary ' + 'x' * 1900,
               'created_at': '2026-10-10T00:00:00+00:00'}
              for index in range(200)]
    assert OllamaChat().select('Which record matters?', events) == ['event-0']
    content = captured['messages'][1]['content']
    assert len(content.encode()) <= 3000
    assert len(json.loads(content)['events']) == 12
    assert 'event-199' not in content
