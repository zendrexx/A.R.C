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
    return not any(fnmatch.fnmatch(normalized, pattern) or fnmatch.fnmatch(name, pattern)
                   for pattern in SENSITIVE_GLOBS)


def current_head(root: Path) -> str:
    return _git(root, "rev-parse", "HEAD", check=False).decode().strip() or "UNBORN"


def current_branch(root: Path) -> str | None:
    name = _git(root, "symbolic-ref", "--quiet", "--short", "HEAD",
                check=False).decode().strip()
    return name or None


def is_ancestor(root: Path, older: str, newer: str) -> bool:
    result = subprocess.run(
        ["git", "-C", str(root), "merge-base", "--is-ancestor", older, newer],
        capture_output=True, check=False, timeout=20,
    )
    return result.returncode == 0


def commits_between(root: Path, older: str, newer: str, limit: int = 200) -> list[str]:
    out = _git(root, "rev-list", "--reverse", f"--max-count={limit}",
               f"{older}..{newer}", check=False)
    return [line.strip() for line in out.decode().splitlines() if line.strip()]


def commit_subject(root: Path, sha: str) -> str:
    return _git(root, "show", "-s", "--format=%s", sha,
                check=False).decode("utf-8", "replace").strip()


def snapshot(project_path: Path) -> GitSnapshot:
    root_text = _git(project_path, "rev-parse", "--show-toplevel").decode().strip()
    root = Path(root_text).resolve()
    head = _git(root, "rev-parse", "HEAD", check=False).decode().strip() or "UNBORN"
    if head == "UNBORN":
        diff = _git(root, "diff", "--binary") + _git(root, "diff", "--cached", "--binary")
        changed = _git(root, "diff", "--name-only", "-z") + _git(
            root, "diff", "--cached", "--name-only", "-z"
        )
    else:
        diff = _git(root, "diff", "--binary", "HEAD")
        changed = _git(root, "diff", "--name-only", "-z", "HEAD")
    untracked = _git(root, "ls-files", "--others", "--exclude-standard", "-z")
    digest = hashlib.sha256()
    digest.update(head.encode())
    digest.update(diff)
    untracked_names = sorted(name for name in untracked.decode("utf-8", "surrogateescape").split("\0") if name)
    for name in untracked_names:
        path = root / name
        digest.update(name.encode("utf-8", "surrogateescape"))
        if path.is_symlink():
            digest.update(os.readlink(path).encode("utf-8", "surrogateescape"))
        elif path.is_file():
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    digest.update(chunk)
    all_changed = {
        name for name in (changed + untracked).decode("utf-8", "surrogateescape").split("\0")
        if name and _visible(name)
    }
    return GitSnapshot(root, head, digest.hexdigest(), tuple(sorted(all_changed)))

