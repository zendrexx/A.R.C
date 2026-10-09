"""Opt-in polling collector. Durable cursors; no file bodies are stored."""
import time
import sqlite3
import sys
from pathlib import Path
from datetime import datetime, timezone

from arc.git_evidence import _git, _visible, snapshot
from arc.memory import EmbeddingUnavailable, redact
from arc.store import utc_now


def status(service, path: Path) -> dict:
    project = service._project(path)
    row = service.store.connection.execute(
        'SELECT * FROM observer_state WHERE project_id=?', (project['id'],)).fetchone()
    return dict(row) if row else {'project_id': project['id'], 'enabled': False, 'paused': False}


def control(service, path: Path, action: str) -> dict:
    if action not in {'enable', 'pause', 'resume', 'disable'}:
        raise ValueError('Unknown observer action')
    project = service._project(path)
    observed = snapshot(path)
    db = service.store.connection
    db.execute('BEGIN IMMEDIATE')
    current = status(service, path)
    if action in {'pause', 'resume'} and not current['enabled']:
        db.rollback()
        raise ValueError('Enable observation explicitly before pausing or resuming.')
    # Resume deliberately discards the paused interval; enable preserves restart cursor.
    baseline = (action in {'resume', 'disable'} or not current.get('fingerprint')
                or (action == 'enable' and (not current['enabled'] or current['paused'])))
    db.execute('''INSERT INTO observer_state VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET enabled=excluded.enabled,
        paused=excluded.paused, fingerprint=excluded.fingerprint,
        head=excluded.head, updated_at=excluded.updated_at''',
        (project['id'], action != 'disable', action == 'pause',
         observed.fingerprint if baseline else current.get('fingerprint'),
         observed.head if baseline else current.get('head'), utc_now()))
    db.commit()
    return status(service, path)


def poll(service, path: Path) -> list[dict]:
    baseline = status(service, path)
    if not baseline['enabled'] or baseline['paused']:
        return []
    observed = snapshot(path)
    commits = []
    metadata = []
    cursor = baseline.get('head')
    if cursor and cursor != observed.head and observed.head != 'UNBORN':
        spec = observed.head if cursor == 'UNBORN' else f'{cursor}..{observed.head}'
        commits = _git(path, 'rev-list', '--reverse', spec, check=False).decode().splitlines()[:100]
        for head in commits:
            paths = _git(path, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', head).decode('utf-8', 'replace').split('\0')
            visible = sorted(p for p in paths if p and _visible(p))
            if not visible:
                continue
            text = _git(path, 'show', '-s', '--format=%cI%n%s', head).decode('utf-8', 'replace')
            committed_at, _, message = text.partition('\n')
            timestamp = datetime.fromisoformat(committed_at).astimezone(timezone.utc).isoformat(timespec='seconds')
            metadata.append((head, visible, redact(message.strip()), timestamp))
    # Gather Git metadata before taking the short SQLite write lock.
    db = service.store.connection
    db.execute('BEGIN IMMEDIATE')
    try:
        current = status(service, path)
        if not current['enabled'] or current['paused']:
            db.rollback()
            return []
        if (current['fingerprint'], current['head']) != (baseline.get('fingerprint'), baseline.get('head')):
            db.rollback()
            return []
        events = []
        if observed.fingerprint != current['fingerprint']:
            for head, visible, message, timestamp in metadata:
                ref = f'git:commit/{head}'
                if db.execute('SELECT 1 FROM events WHERE project_id=? AND source_ref=?', (current['project_id'], ref)).fetchone():
                    continue
                events.append(service.store.add_event(current['project_id'], 'git',
                    f'Commit {head[:8]}: {message}', 'observer_commit', ref,
                    git_head=head, details={'changed_paths': visible, 'has_visible_changes': bool(visible),
                                            'commit_message': message, 'observed_at': utc_now(),
                                            'committed_at': timestamp}, commit=False, created_at=timestamp))
            if (not commits or commits[-1] == observed.head) and (observed.changed_paths or not commits):
                events.append(service.store.add_event(current['project_id'], 'git',
                    'Observed Git changes: ' + (', '.join(observed.changed_paths[:30]) or 'working tree clean'),
                    'observer', 'auto', git_head=observed.head, fingerprint=observed.fingerprint,
                    details={'changed_paths': list(observed.changed_paths),
                             'has_visible_changes': bool(observed.changed_paths)}, commit=False))
            # Keep cursor behind if more than one bounded commit page remains.
            head = commits[-1] if len(commits) == 100 else observed.head
            fingerprint = current['fingerprint'] if head != observed.head else observed.fingerprint
            db.execute('UPDATE observer_state SET fingerprint=?, head=?, updated_at=? WHERE project_id=?',
                       (fingerprint, head, utc_now(), current['project_id']))
        db.commit()
        return events
    except BaseException:
        db.rollback()
        raise


def watch(service, path: Path, interval: float = 5) -> None:
    """SQLite is the durable index queue. Index at most two records per retry."""
    next_index = 0.0
    if not status(service, path)['enabled']:
        return
    if not service.active_session(path):
        try:
            service.start_session(path, 'Automatic observation')
        except ValueError:
            if not service.active_session(path):
                raise
    while True:
        state = status(service, path)
        if not state['enabled']:
            return
        if not state['paused']:
            try:
                poll(service, path)
            except (ValueError, OSError, sqlite3.OperationalError) as error:
                print(f'A.R.C. observer will retry: {error}', file=sys.stderr, flush=True)
                time.sleep(max(1, interval))
                continue
            if time.monotonic() >= next_index:
                try:
                    service.memory.index_pending(state['project_id'], limit=2)
                except EmbeddingUnavailable:
                    pass
                next_index = time.monotonic() + 30
        time.sleep(max(1, interval))
