"""Automatic editor sessions retain evidence across windows and restarts."""

import os
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

from arc.service import ArcService
from arc.observer import control, poll


def test_two_windows_share_a_session_and_close_it_once(sample_repo: Path, tmp_path: Path):
    service = ArcService(tmp_path / 'memory.sqlite3')
    try:
        service.register_project(sample_repo)
        first = service.workspace_open(sample_repo, 'a' * 32, os.getpid())
        second = service.workspace_open(sample_repo, 'b' * 32, os.getpid())
        assert first['session']['id'] == second['session']['id']
        note = service.record_note(sample_repo, 'decision', 'Keep the existing parser')
        assert note['session_id'] == first['session']['id']
        assert service.workspace_close(sample_repo, 'a' * 32)['remaining_windows'] == 1
        assert service.active_session(sample_repo)['id'] == first['session']['id']
        assert service.workspace_close(sample_repo, 'b' * 32)['remaining_windows'] == 0
        assert service.active_session(sample_repo) is None
        handoff = service.project_handoff(sample_repo)
        assert handoff['previous_session']['session']['id'] == first['session']['id']
        assert handoff['previous_session']['recent_evidence'][0]['id'] == note['id']
        assert handoff['latest_checkpoint'] is not None
    finally:
        service.close()


def test_stale_owner_is_recovered_on_next_open(sample_repo: Path, tmp_path: Path):
    service = ArcService(tmp_path / 'memory.sqlite3')
    try:
        service.register_project(sample_repo)
        old = service.workspace_open(sample_repo, 'c' * 32, 99999999)['session']
        service.record_note(sample_repo, 'note', 'Before the crash')
        new = service.workspace_open(sample_repo, 'd' * 32, os.getpid())
        assert new['recovered_previous_session'] is True
        assert new['session']['id'] != old['id']
        assert service.store.get_session(old['id'])['ended_at'] is not None
        assert service.project_handoff(sample_repo)['previous_session']['session']['id'] == old['id']
    finally:
        service.close()


def test_idle_rotation_and_periodic_checkpoint(sample_repo: Path, tmp_path: Path):
    service = ArcService(tmp_path / 'memory.sqlite3')
    try:
        project = service.register_project(sample_repo)
        owner = 'e' * 32
        old = service.workspace_open(sample_repo, owner, os.getpid())['session']
        past = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat(timespec='seconds')
        service.store.connection.execute('UPDATE sessions SET last_activity_at=? WHERE id=?',
                                         (past, old['id']))
        service.store.connection.commit()
        note = service.record_note(sample_repo, 'note', 'After an idle period')
        assert note['session_id'] != old['id']
        assert service.store.get_session(old['id'])['ended_at'] == past
        service.store.connection.execute('UPDATE sessions SET last_checkpoint_at=? WHERE id=?',
                                         (past, note['session_id']))
        service.store.connection.commit()
        touched = service.workspace_touch(sample_repo, owner)
        assert touched['checkpoint_due'] is True
        first_checkpoint = service.store.latest_checkpoint(project['id'])['id']
        assert service.workspace_touch(sample_repo, owner)['checkpoint_due'] is False
        assert service.store.latest_checkpoint(project['id'])['id'] == first_checkpoint
    finally:
        service.close()


def test_nested_folder_resolves_registered_git_root(sample_repo: Path, tmp_path: Path):
    service = ArcService(tmp_path / 'memory.sqlite3')
    try:
        service.register_project(sample_repo)
        nested = sample_repo / 'src'
        nested.mkdir()
        opened = service.workspace_open(nested, 'f' * 32, os.getpid())
        assert opened['handoff']['project']['path'] == str(sample_repo)
        service.workspace_close(nested, 'f' * 32)
    finally:
        service.close()


def test_observer_deduplicates_and_respects_project_exclusions(sample_repo: Path, tmp_path: Path):
    service = ArcService(tmp_path / 'memory.sqlite3')
    try:
        service.register_project(sample_repo)
        control(service, sample_repo, 'enable')
        (sample_repo / '.arcignore').write_text('private/*\n')
        (sample_repo / 'private').mkdir()
        (sample_repo / 'private' / 'notes.txt').write_text('hidden')
        (sample_repo / '.env').write_text('SECRET=hidden')
        (sample_repo / 'visible.txt').write_text('first')
        events = poll(service, sample_repo)
        assert len(events) == 1
        assert events[0]['details']['changed_files'] == [
            {'path': 'visible.txt', 'status': 'created'}]
        assert poll(service, sample_repo) == []
        subprocess.run(['git', '-C', str(sample_repo), 'mv', 'app.py', 'renamed.py'], check=True)
        events = poll(service, sample_repo)
        renamed = [item for item in events[0]['details']['changed_files'] if item['status'] == 'renamed']
        assert renamed == [{'path': 'renamed.py', 'status': 'renamed', 'from_path': 'app.py'}]
        subprocess.run(['git', '-C', str(sample_repo), 'checkout', '-qb', 'next-work'], check=True)
        events = poll(service, sample_repo)
        assert len(events) == 1
        assert events[0]['details']['branch'] == 'next-work'
    finally:
        service.close()
