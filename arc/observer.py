"""Opt-in polling collector. Durable cursors; no file bodies are stored."""
import os
import signal
import sqlite3
import subprocess
import sys
import time
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path

from arc.git_evidence import _git, _visible, branch_name, changed_file_statuses, exclusion_globs, is_ancestor, snapshot
from arc.memory import EmbeddingUnavailable, redact
from arc.store import utc_now


def _alive(pid) -> bool:
    try:
        os.kill(int(pid), 0)
    except (OSError, TypeError, ValueError):
        return False
    # A dead worker launched by this process stays a zombie until reaped;
    # os.kill(pid, 0) still succeeds for zombies.
    try:
        reaped, _ = os.waitpid(int(pid), os.WNOHANG)
        return reaped != int(pid)
    except (ChildProcessError, OSError):
        return True


def status(service, path: Path) -> dict:
    project = service._project(path)
    row = service.store.connection.execute(
        'SELECT * FROM observer_state WHERE project_id=?', (project['id'],)).fetchone()
    state = dict(row) if row else {'project_id': project['id'], 'enabled': False,
                                   'paused': False, 'worker_pid': None}
    state['worker_alive'] = _alive(state.get('worker_pid'))
    return state


def control(service, path: Path, action: str) -> dict:
    if action not in {'enable', 'pause', 'resume', 'disable'}:
        raise ValueError('Unknown observer action')
    project = service._project(path)
    observed = snapshot(path)
    branch = branch_name(observed.root)
    db = service.store.connection
    db.execute('BEGIN IMMEDIATE')
    current = status(service, path)
    if action in {'pause', 'resume'} and not current['enabled']:
        db.rollback()
        raise ValueError('Enable observation explicitly before pausing or resuming.')
    # Resume deliberately discards the paused interval; enable preserves restart cursor.
    baseline = (action in {'resume', 'disable'} or not current.get('fingerprint')
                or (action == 'enable' and (not current['enabled'] or current['paused'])))
    db.execute('''INSERT INTO observer_state
        (project_id, enabled, paused, fingerprint, head, branch, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(project_id) DO UPDATE SET enabled=excluded.enabled,
        paused=excluded.paused, fingerprint=excluded.fingerprint,
        head=excluded.head, branch=excluded.branch, updated_at=excluded.updated_at''',
        (project['id'], action != 'disable', action == 'pause',
         observed.fingerprint if baseline else current.get('fingerprint'),
         observed.head if baseline else current.get('head'),
         branch if baseline else current.get('branch'), utc_now()))
    db.commit()
    return status(service, path)


def poll(service, path: Path) -> list[dict]:
    baseline = status(service, path)
    if not baseline['enabled'] or baseline['paused']:
        return []
    observed = snapshot(path)
    branch = branch_name(observed.root)
    file_statuses = changed_file_statuses(observed.root) if observed.changed_paths else []
    extra_globs = exclusion_globs(observed.root)
    commits = []
    metadata = []
    cursor = baseline.get('head')
    if cursor and cursor != observed.head and observed.head != 'UNBORN':
        # Recover only commits that descend from the cursor; a rebase, amend, or
        # checkout moves HEAD without a fast-forward and is a baseline change,
        # not a list of new commits.
        if cursor == 'UNBORN' or is_ancestor(path, cursor, observed.head):
            spec = observed.head if cursor == 'UNBORN' else f'{cursor}..{observed.head}'
            commits = _git(path, 'rev-list', '--reverse', spec, check=False).decode().splitlines()[:100]
            for head in commits:
                paths = _git(path, 'diff-tree', '--root', '--no-commit-id', '--name-only', '-r', '-z', head).decode('utf-8', 'replace').split('\0')
                visible = sorted(p for p in paths if p and _visible(p, extra_globs))
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
        if (current['fingerprint'], current['head'], current.get('branch')) != (baseline.get('fingerprint'), baseline.get('head'), baseline.get('branch')):
            db.rollback()
            return []
        events = []
        if branch != current.get('branch'):
            events.append(service.store.add_event(current['project_id'], 'git',
                f'Git branch: {redact(current.get("branch") or "unknown")} → {redact(branch)}',
                'observer', 'auto', git_head=observed.head,
                details={'previous_branch': current.get('branch'), 'branch': branch,
                         'has_visible_changes': False}, commit=False))
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
                             'changed_files': file_statuses,
                             'has_visible_changes': bool(observed.changed_paths)}, commit=False))
            # Keep cursor behind if more than one bounded commit page remains.
            head = commits[-1] if len(commits) == 100 else observed.head
            fingerprint = current['fingerprint'] if head != observed.head else observed.fingerprint
            db.execute('UPDATE observer_state SET fingerprint=?, head=?, branch=?, updated_at=? WHERE project_id=?',
                       (fingerprint, head, branch, utc_now(), current['project_id']))
        elif branch != current.get('branch'):
            db.execute('UPDATE observer_state SET branch=?, updated_at=? WHERE project_id=?',
                       (branch, utc_now(), current['project_id']))
        db.commit()
        return events
    except BaseException:
        db.rollback()
        raise


def launch(service, path: Path, interval: float | None = None) -> dict:
    """Enable observation and start a detached 'arc watch' worker if none runs."""
    project = service._project(path)
    current = status(service, path)
    if not current['enabled']:
        current = control(service, path, 'enable')
    if _alive(current.get('worker_pid')):
        return {**current, 'launched': False,
                'note': 'Observer worker is already running; no second worker started.'}
    log_path = service.store.path.parent / f'observer-{project["id"]}.log'
    env = dict(os.environ)
    env['PYTHONIOENCODING'] = 'utf-8'
    env['PYTHONPATH'] = (str(Path(__file__).resolve().parent.parent)
                         + os.pathsep + env.get('PYTHONPATH', ''))
    argv = [sys.executable, '-m', 'arc.cli', '--project', project['path'],
            '--db', str(service.store.path), 'watch']
    if interval:
        argv += ['--interval', str(interval)]
    with log_path.open('ab') as target:
        child = subprocess.Popen(argv, cwd=project['path'], env=env,
                                 stdin=subprocess.DEVNULL, stdout=target,
                                 stderr=subprocess.STDOUT, start_new_session=True,
                                 close_fds=True)
    # Record the pid immediately so a second launch does not spawn a duplicate
    # before the child has booted and registered itself in watch().
    service.store.connection.execute(
        'UPDATE observer_state SET worker_pid=? WHERE project_id=?',
        (child.pid, project['id']))
    service.store.connection.commit()
    return {**status(service, path), 'launched': True,
            'log': str(log_path)}


def stop_worker(service, path: Path) -> dict:
    """Disable observation and terminate a running worker process."""
    result = control(service, path, 'disable')
    pid = result.get('worker_pid')
    stopped = False
    if _alive(pid):
        try:
            os.kill(int(pid), signal.SIGTERM)
            stopped = True
        except OSError:
            pass
    if not _alive(pid):
        service.store.connection.execute(
            'UPDATE observer_state SET worker_pid=NULL WHERE project_id=?',
            (result['project_id'],))
        service.store.connection.commit()
    return {**status(service, path), 'terminated_worker': stopped}


def watch(service, path: Path, interval: float = 5) -> None:
    """SQLite is the durable index queue. Index at most two records per retry."""
    next_index = 0.0
    state = status(service, path)
    if not state['enabled']:
        return
    db = service.store.connection
    pid = os.getpid()
    owner_id = uuid4().hex
    service.workspace_open(path, owner_id, pid)
    previous_sigterm = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda _signum, _frame: (_ for _ in ()).throw(SystemExit(0)))
    db.execute('UPDATE observer_state SET worker_pid=? WHERE project_id=?',
               (pid, state['project_id']))
    db.commit()
    try:
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
            try:
                service.workspace_touch(path, owner_id)
            except ValueError as error:
                if 'expired' not in str(error):
                    raise
                service.workspace_open(path, owner_id, pid)
            time.sleep(max(1, interval))
    finally:
        signal.signal(signal.SIGTERM, previous_sigterm)
        try:
            service.workspace_close(path, owner_id)
        finally:
            db.execute('UPDATE observer_state SET worker_pid=NULL '
                       'WHERE project_id=? AND worker_pid=?', (state['project_id'], pid))
            db.commit()
