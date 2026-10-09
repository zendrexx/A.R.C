"""Checking editor ownership must never terminate the editor process."""
import subprocess
import sys

from arc.store import Store


def test_liveness_check_keeps_process_running():
    child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])
    try:
        for _ in range(3):
            assert Store._pid_alive(child.pid)
            assert child.poll() is None
        child.terminate()
        child.wait(timeout=10)
        assert not Store._pid_alive(child.pid)
    finally:
        if child.poll() is None:
            child.terminate()
        child.wait(timeout=10)


def test_invalid_process_ids_are_not_alive():
    for pid in (None, 0, -1, 'invalid'):
        assert not Store._pid_alive(pid)
