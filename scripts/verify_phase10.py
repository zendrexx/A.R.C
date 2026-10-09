"""Exercise Phase 10 questions with local models and no external network.

Prepare A.R.C., Ollama, and both models before disconnecting. The script reads
the selected project, validates source IDs, and saves a compact JSON report.
"""

import argparse
import json
import platform
import socket
import subprocess
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from time import perf_counter

from arc.chat import answer
from arc.service import ArcService


QUESTIONS = (
    'What happened today?',
    'What changed yesterday?',
    'What errors did we fix?',
    'Why did we implement this feature?',
    'Where did we leave off?',
    'Summarize our development timeline.',
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', type=Path, required=True)
    parser.add_argument('--db', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--timezone-offset', type=int, default=480)
    parser.add_argument('--expected-rationale-event',
                        help='known event ID for a named rationale question')
    parser.add_argument('--require-wifi-off', action='store_true')
    args = parser.parse_args()
    project, database = args.project.resolve(), args.db.resolve()
    zone = timezone(timedelta(minutes=args.timezone_offset))
    report = {'date_local': datetime.now(zone).isoformat(),
              'machine': platform.platform(), 'project': project.name,
              'database': database.name, 'wifi_power': None,
              'external_tcp_connected': None, 'results': []}
    service = None
    try:
        power = subprocess.run(['networksetup', '-getairportpower', 'en0'],
                               capture_output=True, text=True, check=True,
                               timeout=5).stdout.strip()
        report['wifi_power'] = power
        if args.require_wifi_off and not power.endswith(': Off'):
            raise RuntimeError('Wi-Fi must be off for this physical trial')
        try:
            with socket.create_connection(('1.1.1.1', 443), timeout=2):
                report['external_tcp_connected'] = True
        except OSError:
            report['external_tcp_connected'] = False
        if report['external_tcp_connected']:
            raise RuntimeError('External TCP was reachable')
        service = ArcService(database)
        service._project(project)
        questions = (*QUESTIONS,
                     *(['Why did we use a local browser dashboard instead of another service?']
                       if args.expected_rationale_event else []))
        now = datetime.now(zone)
        for question in questions:
            started = perf_counter()
            result = answer(service, project, question,
                            offset_minutes=args.timezone_offset, now=now)
            for citation in result['citations']:
                event = service.get_event(project, citation['id'])
                if event['source_ref'] != citation['source_ref']:
                    raise RuntimeError(f"Citation {citation['id']} did not resolve")
            if question == QUESTIONS[0] or question == QUESTIONS[1]:
                local_day = now.date() - timedelta(days=question == QUESTIONS[1])
                start = datetime.combine(local_day, time.min, zone)
                if (result['since'] != start.astimezone(timezone.utc).isoformat()
                        or result['until'] != (start + timedelta(days=1)).astimezone(
                            timezone.utc).isoformat()):
                    raise RuntimeError(f'Incorrect local calendar range for {question}')
            if question == QUESTIONS[2]:
                if ('No reported resolution' not in result['answer']
                        and 'do not prove the error is fixed' not in result['answer']):
                    raise RuntimeError('Error answer did not distinguish reported fixes')
            if question == QUESTIONS[3]:
                if (result['citations'] or
                        result['answer'] != 'No recorded rationale supports this answer.'):
                    raise RuntimeError('Ambiguous rationale question invented supporting evidence')
            if question == QUESTIONS[4] and result['retrieval_mode'] != 'handoff':
                raise RuntimeError('Continuation question missed the handoff path')
            if question == QUESTIONS[5]:
                if result['retrieval_mode'] != 'timeline':
                    raise RuntimeError('Timeline question missed bounded history')
                if result['next_offset'] is not None:
                    following = answer(service, project, question,
                        offset_minutes=args.timezone_offset,
                        offset=result['next_offset'],
                        snapshot_rowid=result['snapshot_rowid'], now=now)
                    if (following['snapshot_rowid'] != result['snapshot_rowid']
                            or following['next_offset'] is not None
                            and following['next_offset'] <= result['next_offset']):
                        raise RuntimeError('Timeline continuation was unstable')
            if args.expected_rationale_event and question == questions[-1]:
                if args.expected_rationale_event not in {
                        citation['id'] for citation in result['citations']}:
                    raise RuntimeError('Known recorded rationale was not cited')
            report['results'].append({
                'question': question, 'mode': result['mode'],
                'retrieval_mode': result['retrieval_mode'],
                'citation_ids': [citation['id'] for citation in result['citations']],
                'total_events': result['total_events'],
                'total_entries': result['total_entries'],
                'next_offset': result['next_offset'],
                'elapsed_ms': round((perf_counter() - started) * 1000, 1),
            })
        report['status'] = 'passed'
    except Exception as error:
        report['status'] = 'failed'
        report['error'] = str(error)
    finally:
        if service:
            service.close()
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, indent=2))
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
