"""Read-only Git observations. No source content is stored in A.R.C."""

import fnmatch
import hashlib
import os
import subprocess
from pathlib import Path

from arc.contracts import GitSnapshot

SENSITIVE_GLOBS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*credentials*",
    "*secret*", "*.sqlite", "*.sqlite3", "*.db", ".arc/*",
)
GENERATED_DIRS = {'.git', '.arc', '.venv', 'node_modules', '__pycache__',
                  '.pytest_cache', 'out', 'build', 'dist'}


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    result = subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, check=False, timeout=20
    )
    if check and result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "Git failed")
    return result.stdout if result.returncode == 0 else b""


def _visible(path: str) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    return not any(part in GENERATED_DIRS for part in normalized.split('/')) and not any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern)
                   for pattern in SENSITIVE_GLOBS)


def is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", older, newer],
        capture_output=True, check=False, timeout=20,
    )
    return result.returncode == 0


def snapshot(project_path: Path) -> GitSnapshot:
    root_text = _git(project_path, "rev-parse", "--show-toplevel").decode().strip()
    root = Path(root_text).resolve()
    head = _git(root, "rev-parse", "HEAD", check=False).decode().strip() or "UNBORN"
    if head == "UNBORN":
        changed = _git(root, "diff", "--name-only", "-z") + _git(
            root, "diff", "--cached", "--name-only", "-z"
        )
    else:
        changed = _git(root, "diff", "--name-only", "-z", "HEAD")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    digest = hashlib.sha256()
    digest.update(head.encode())
    all_changed = {
        name for name in (changed + untracked).decode("utf-8", "surrogateescape").split("\0")
        if name and _visible(name)
    }
    # Hash only eligible paths, before reading any content. No diff is retained.
    for name in sorted(all_changed):
        path = root / name
        digest.update(name.encode("utf-8", "surrogateescape"))
        digest.update(_git(root, 'ls-files', '--stage', '--', name))
        if path.is_symlink():
            digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        elif path.is_file():
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
    return GitSnapshot(root, head, digest.hexdigest(), tuple(sorted(all_changed)))

