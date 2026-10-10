"""Share of commits carrying a coding-agent co-authorship trailer (Sections 1 and 5).

A commit counts if its message matches 'Co-Authored-By: Claude' case-insensitively.
This is a lower bound on agent involvement: agent-assisted commits without a
trailer exist. Merge and squash handling follows plain `git log` (all commits
reachable from HEAD, merges included).
Usage: python agent_trailers.py --repo PATH [--ref SNAPSHOT] [--since 2026-09-16]
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _git import git


def count(repo: Path, extra: list[str], ref: str) -> tuple[int, int]:
    total = len(git(repo, "rev-list", *extra, ref).split())
    agent = len(git(repo, "log", "--format=%H", "-i", "--grep=co-authored-by: claude", *extra, ref).split())
    return total, agent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--since")
    ap.add_argument("--ref", default="HEAD", help="snapshot commit used in the paper")
    a = ap.parse_args()
    extra = [f"--since={a.since}"] if a.since else []
    total, agent = count(a.repo.expanduser(), extra, a.ref)
    print(f"commits={total} agent_trailer={agent} share={agent / total:.1%}")


if __name__ == "__main__":
    main()
