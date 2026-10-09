"""Repeatable installed-package workflow in an isolated disposable Git project.

Run after installing the current package: python -m scripts.validate_phase12.
Resource samples cover the Python observer only, excluding Git/model processes.
This does not certify physical disconnection, VS Code appearance, or Mac budgets.
"""
import argparse
import asyncio
import json
import os
import platform
import shlex
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from datetime import datetime, timezone
from pathlib import Path


def sample_process(process):
    if sys.platform == 'win32':
        shell = shutil.which('pwsh') or str(Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/WindowsPowerShell/v1.0/powershell.exe')
        command = (f'$sampleIds = @({process.pid}); '
                   f'$childIds = Get-CimInstance Win32_Process | Where-Object {{ $_.ParentProcessId -eq {process.pid} -and $_.Name -like "python*" }} | Select-Object -ExpandProperty ProcessId; '
                   '$sampleIds += @($childIds); Get-Process -Id $sampleIds | Select-Object CPU,WorkingSet64 | ConvertTo-Json')
        result = subprocess.run([shell, '-NoProfile', '-Command', command],
            capture_output=True, text=True, check=True, timeout=15)
        data = json.loads(result.stdout)
        samples = data if isinstance(data, list) else [data]
        return {'cpu_seconds': sum(item['CPU'] or 0 for item in samples),
                'rss_bytes': sum(item['WorkingSet64'] for item in samples)}
    result = subprocess.run(['ps', '-p', str(process.pid), '-o', 'rss=', '-o', 'cputime='],
                            capture_output=True, text=True, check=True, timeout=10)
    rss, cpu = result.stdout.split()
    days, _, clock = cpu.rpartition('-')
    parts = list(reversed(clock.split(':')))
    seconds = sum(float(value) * 60 ** i for i, value in enumerate(parts))
    return {'cpu_seconds': seconds + (int(days) * 86400 if days else 0), 'rss_bytes': int(rss) * 1024}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, default=Path('.arc/phase12-report.json'))
    args = parser.parse_args()
    report = {'machine': platform.platform(), 'python': sys.version.split()[0],
              'date_utc': datetime.now(timezone.utc).isoformat(), 'checks': {}, 'measurements': {},
              'limits': ['Observer samples exclude spawned Git and Ollama processes.',
                         'Physical network disconnection and target Mac M1 8GB checks are pending.',
                         'VS Code visual and keyboard checks require an extension host.',
                         'Local chat quotes evidence; Ollama source selection is optional.']}
    checks, measurements = report['checks'], report['measurements']
    environment = os.environ.copy()
    environment.pop('PYTHONPATH', None)
    environment['PYTHONIOENCODING'] = 'utf-8'
    worker = None
    with tempfile.TemporaryDirectory(prefix='arc-phase12-') as directory:
        folder = Path(directory).resolve()
        repo, database = folder / 'project', folder / 'arc.sqlite3'
        repo.mkdir()

        def git(*arguments):
            return subprocess.run(['git', '-C', str(repo), *arguments], capture_output=True,
                                  text=True, check=True, timeout=30).stdout

        def cli(*arguments):
            result = subprocess.run([sys.executable, '-m', 'arc.cli', '--project', str(repo),
                '--db', str(database), *arguments], cwd=repo, env=environment,
                capture_output=True, text=True, encoding='utf-8', check=True, timeout=180)
            return json.loads(result.stdout)

        def events():
            with closing(sqlite3.connect(database)) as db:
                db.row_factory = sqlite3.Row
                return [dict(row) for row in db.execute('SELECT * FROM events ORDER BY rowid')]

        def wait_for(predicate, timeout=25):
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                if predicate():
                    return
                if worker is not None and worker.poll() is not None:
                    raise RuntimeError('Observer stopped unexpectedly')
                time.sleep(0.2)
            raise RuntimeError('Timed out waiting for observer evidence')

        def start_worker():
            return subprocess.Popen([sys.executable, '-m', 'arc.cli', '--project', str(repo),
                '--db', str(database), 'watch'], cwd=repo, env=environment,
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        def stop_worker(process):
            if process and process.poll() is None:
                if sys.platform == 'win32':
                    taskkill = Path(os.environ.get('SystemRoot', r'C:\Windows')) / 'System32/taskkill.exe'
                    subprocess.run([str(taskkill), '/PID', str(process.pid), '/T', '/F'],
                                   capture_output=True, check=False, timeout=10)
                else:
                    process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)

        git('init', '-q')
        git('config', 'user.name', 'A.R.C. Validation')
        git('config', 'user.email', 'validation@example.invalid')
        (repo / 'app.py').write_text('print("initial")\n')
        git('add', 'app.py')
        git('commit', '-qm', 'initial')
        report['installed_backend'] = subprocess.run([sys.executable, '-c',
            'import arc; print(arc.__file__)'], cwd=repo, env=environment,
            capture_output=True, text=True, check=True).stdout.strip()
        cli('init')
        cli('observer', 'enable')
        try:
            worker = start_worker()
            wait_for(lambda: cli('session', 'status') is not None)
            first = sample_process(worker)
            started = time.monotonic()
            time.sleep(5)
            last = sample_process(worker)
            elapsed = time.monotonic() - started
            measurements['observer_python_idle_cpu_percent'] = round(
                (last['cpu_seconds'] - first['cpu_seconds']) / elapsed * 100, 3)
            measurements['observer_python_rss_bytes'] = last['rss_bytes']
            measurements['idle_sample_seconds'] = round(elapsed, 3)

            started = time.monotonic()
            (repo / 'app.py').write_text('print("saved")\n')
            wait_for(lambda: any(e['source'] == 'observer' for e in events()))
            measurements['save_observation_seconds'] = round(time.monotonic() - started, 3)
            count = len(events())
            for _ in range(10):
                (repo / 'app.py').write_text('print("saved")\n')
            (repo / '.env').write_text('TOKEN=synthetic-excluded-value\n')
            time.sleep(6)
            assert len(events()) == count
            checks['unchanged_saves_deduplicated_and_env_excluded'] = True

            stop_worker(worker)
            worker = None
            git('add', 'app.py')
            git('commit', '-qm', 'commit made while observer stopped')
            worker = start_worker()
            wait_for(lambda: any(e['source'] == 'observer_commit' for e in events()))
            assert len([e for e in events() if e['source'] == 'observer_commit']) == 1
            checks['external_commit_recovered_after_worker_restart'] = True

            task = cli('task', 'add', 'Synthetic validation task')
            cli('task', 'claim', task['id'], 'The task is complete')
            (repo / 'app.py').write_text('print("failing version")\n')
            cli('capture', '--task', task['id'])
            command = shlex.quote(sys.executable)
            cli('init', '--test-command', command + ' -c "raise SystemExit(1)"')
            failed = cli('test', '--task', task['id'])
            assert failed['details']['passed'] is False
            (repo / 'app.py').write_text('print("fixed version")\n')
            cli('capture', '--task', task['id'])
            cli('init', '--test-command', command + ' -c "print(123)"')
            passed = cli('test', '--task', task['id'])
            assert passed['details']['passed'] is True
            state = cli('state')['tasks'][0]
            assert state['state'] == 'tests_passed' and not state['confirmed_by_user']
            checks['failing_then_passing_test_retains_unconfirmed_task'] = True

            cli('observer', 'pause')
            count = len(events())
            (repo / 'app.py').write_text('print("paused interval")\n')
            git('add', 'app.py')
            git('commit', '-qm', 'deliberately excluded paused activity')
            time.sleep(6)
            assert len(events()) == count
            cli('observer', 'resume')
            time.sleep(6)
            assert len(events()) == count
            checks['pause_and_resume_discard_paused_activity'] = True

            started = time.monotonic()
            answer = cli('chat', 'Where did we leave off?', '--keyword-only')
            measurements['evidence_chat_cli_seconds'] = round(time.monotonic() - started, 3)
            assert answer['citations'] and 'Unverified claim' in answer['answer']
            for citation in answer['citations']:
                assert cli('event', citation['id'])['id'] == citation['id']
            checks['chat_citations_resolve_and_claims_stay_unverified'] = True
            missing = cli('chat', 'Why did we choose an unrelated renderer?', '--keyword-only')
            assert not missing['citations']
            checks['missing_rationale_is_not_invented'] = True
            started = time.monotonic()
            search = cli('search', 'Synthetic validation', '--keyword-only')
            measurements['keyword_search_cli_seconds'] = round(time.monotonic() - started, 3)
            assert search['mode'] == 'keyword'
            checks['keyword_search_without_models'] = True

            async def fresh_mcp():
                from mcp import ClientSession, StdioServerParameters
                from mcp.client.stdio import stdio_client
                env = {**environment, 'ARC_PROJECT': str(repo), 'ARC_DB': str(database)}
                parameters = StdioServerParameters(command=sys.executable,
                    args=['-m', 'arc.mcp_server'], env=env, cwd=str(repo))
                async with stdio_client(parameters) as (read, write):
                    async with ClientSession(read, write) as client:
                        await client.initialize()
                        result = await client.call_tool('arc_get_timeline', {})
                        assert not result.is_error
                        assert passed['id'] in str(result)
                        result = await client.call_tool('arc_get_event', {'event_id': passed['id']})
                        assert not result.is_error and passed['id'] in str(result)
            asyncio.run(fresh_mcp())
            checks['fresh_mcp_reads_same_evidence_ids'] = True
            cli('observer', 'disable')
            worker.wait(timeout=10)
            assert worker.returncode == 0
            checks['disable_stops_worker'] = True
            measurements['sqlite_bytes'] = database.stat().st_size
            measurements['duplicate_commit_events'] = 0
            measurements['events_recorded'] = len(events())
        finally:
            stop_worker(worker)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
