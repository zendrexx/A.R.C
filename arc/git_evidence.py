"""Read-only Git observations. No source content is stored in A.R.C."""

import fnmatch
import hashlib
import os
import shutil
import subprocess
from pathlib import Path

from arc.contracts import GitSnapshot

SENSITIVE_GLOBS = (
    ".env", ".env.*", "*.pem", "*.key", "*.p12", "*credentials*",
    "*secret*", "*.sqlite", "*.sqlite3", "*.db", ".arc/*", ".arcignore",
)
GENERATED_DIRS = {'.git', '.arc', '.venv', 'node_modules', '__pycache__',
                  '.pytest_cache', 'out', 'build', 'dist'}


def _git_bin() -> str:
    found = shutil.which("git")
    if found:
        return found
    for candidate in ("/usr/bin/git", "/usr/local/bin/git", "/opt/homebrew/bin/git"):
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    raise ValueError("Git executable not found on PATH")


def _git(root: Path, *args: str, check: bool = True) -> bytes:
    try:
        result = subprocess.run(
            [_git_bin(), "-C", str(root), *args], capture_output=True, check=False, timeout=20
        )
    except FileNotFoundError:
        raise ValueError("Git executable not found on PATH") from None
    if check and result.returncode != 0:
        raise ValueError(result.stderr.decode("utf-8", "replace").strip() or "Git failed")
    return result.stdout if result.returncode == 0 else b""


def exclusion_globs(root: Path) -> tuple[str, ...]:
    """Extra exclusion patterns from the project's optional .arcignore file."""
    target = root / '.arcignore'
    if not target.is_file() or target.is_symlink() or target.stat().st_size > 64 * 1024:
        return ()
    lines = target.read_text(encoding='utf-8', errors='replace').splitlines()
    return tuple(line.strip().lower().replace('\\', '/') for line in lines[:512]
                 if line.strip() and not line.lstrip().startswith(('#', '!'))
                 and len(line) <= 256)


def _visible(path: str, extra_globs: tuple[str, ...] = ()) -> bool:
    normalized = path.replace("\\", "/").lower()
    name = Path(normalized).name
    if any(part in GENERATED_DIRS for part in normalized.split('/')):
        return False
    for pattern in (*SENSITIVE_GLOBS, *extra_globs):
        if (fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern)
                or (pattern.endswith('/') and normalized.startswith(pattern))):
            return False
    return True


def is_ancestor(root: Path, older: str, newer: str) -> bool:
    try:
        result = subprocess.run(
            [_git_bin(), "-C", str(root), "merge-base", "--is-ancestor", older, newer],
            capture_output=True, check=False, timeout=20,
        )
    except FileNotFoundError:
        raise ValueError("Git executable not found on PATH") from None
    return result.returncode == 0


def branch_name(root: Path) -> str:
    return _git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', check=False).decode(
        'utf-8', 'replace').strip() or '(detached HEAD)'


def changed_file_statuses(root: Path) -> list[dict]:
    """Eligible Git paths and change types; no file content or diff is read."""
    fields = _git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all').decode(
        'utf-8', 'surrogateescape').split('\0')
    result = []
    extra_globs = exclusion_globs(root)
    index = 0
    while index < len(fields) and fields[index]:
        entry = fields[index]
        code, path = entry[:2], entry[3:]
        original = None
        if 'R' in code or 'C' in code:
            index += 1
            original = fields[index] if index < len(fields) else None
        index += 1
        if not _visible(path, extra_globs) or (original and not _visible(original, extra_globs)):
            continue
        kind = ('renamed' if 'R' in code else 'copied' if 'C' in code else
                'deleted' if 'D' in code else 'created' if code == '??' or 'A' in code else
                'modified')
        item = {'path': path, 'status': kind}
        if original:
            item['from_path'] = original
        result.append(item)
    return result


def snapshot(project_path: Path) -> GitSnapshot:
    root_text = _git(project_path, "rev-parse", "--show-toplevel").decode().strip()
    root = Path(root_text).resolve()
    extra_globs = exclusion_globs(root)
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
        if name and _visible(name, extra_globs)
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

