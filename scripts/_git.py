"""Small git helpers shared by the measurement scripts (stdlib only)."""
from __future__ import annotations

import subprocess
from pathlib import Path


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True).stdout


def commit_before(repo: Path, when: str, ref: str = "HEAD") -> str | None:
    """Last commit reachable from `ref` with committer date at or before `when`."""
    sha = git(repo, "rev-list", "-1", f"--before={when}", ref).strip()
    return sha or None


def show(repo: Path, sha: str, path: str) -> str:
    try:
        return git(repo, "show", f"{sha}:{path}")
    except subprocess.CalledProcessError:
        return ""


def ls_tree(repo: Path, sha: str, path: str, recursive: bool = False) -> list[str]:
    args = ["ls-tree", "--name-only"] + (["-r"] if recursive else []) + [sha, path]
    try:
        return [p for p in git(repo, *args).splitlines() if p]
    except subprocess.CalledProcessError:
        return []
