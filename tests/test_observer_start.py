"""Detached observer worker lifecycle: launch, record, stop."""
import time

import pytest

from arc.observer import _alive, launch, status, stop_worker
from arc.service import ArcService


@pytest.fixture
def service(sample_repo, tmp_path):
    instance = ArcService(tmp_path / 'start.sqlite3')
    instance.register_project(sample_repo)
    yield instance
    try:
        stop_worker(instance, sample_repo)
    except Exception:
        pass
    instance.close()


def test_detached_worker_records_then_stops(service, sample_repo):
    result = launch(service, sample_repo)
    assert result['launched'] is True
    pid = result['worker_pid']
    for _ in range(50):
        if _alive(pid):
            break
        time.sleep(0.1)
    assert _alive(pid)
    assert launch(service, sample_repo)['launched'] is False

    (sample_repo / 'watched.txt').write_text('observed\n')
    deadline = time.time() + 15
    project_id = service._project(sample_repo)['id']
    recorded = []
    while time.time() < deadline:
        recorded = service.store.events(project_id)
        if any('Observed Git changes' in event['summary'] for event in recorded):
            break
        time.sleep(0.3)
    assert any('Observed Git changes' in event['summary'] for event in recorded)

    stopped = stop_worker(service, sample_repo)
    for _ in range(50):
        if not _alive(pid):
            break
        time.sleep(0.1)
    assert stopped['terminated_worker'] is True
    assert not _alive(pid)
    final = status(service, sample_repo)
    assert not final['enabled']
    assert final['worker_alive'] is False
