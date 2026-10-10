"""When five Salli domains first appeared in the core, API, CLI and web client (Section 5.2).

First-touch committer timestamps (local time) per surface:
  core -- src/salli/domain/<d> or application/services/<d>_service.py
  api  -- src/salli/interfaces/api/routers/<router>.py
  cli  -- first commit whose diff adds '<d>_app' to src/salli/interfaces/cli/main.py
  web  -- clients/web/src/app/(app)/<router or d>
Usage: python feature_timeline_salli.py --repo ~/Documents/leafmonkeylabs/salli > ../data/salli_feature_timeline.csv
"""
from __future__ import annotations

import argparse
from pathlib import Path

from _git import git

FEATURES = [("budget", "budget"), ("debt", "debt"), ("portfolio", "portfolio"),
            ("subscription", "subscriptions"), ("insurance", "insurance")]
FMT = "--date=format-local:%Y-%m-%d %H:%M"


REF = "HEAD"


def first(repo: Path, *args: str) -> str:
    out = git(repo, "log", "--reverse", "--format=%cd", FMT, REF, *args).splitlines()
    return out[0] if out else ""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--ref", default="HEAD")
    args = ap.parse_args()
    global REF
    REF = args.ref
    repo = args.repo.expanduser()
    print("feature,core,api,cli,web")
    for d, r in FEATURES:
        core = first(repo, "--", f"src/salli/domain/{d}", f"src/salli/application/services/{d}_service.py")
        api = first(repo, "--", f"src/salli/interfaces/api/routers/{r}.py")
        cli = first(repo, f"-S{d}_app", "--", "src/salli/interfaces/cli/main.py")
        web = first(repo, "--", f"clients/web/src/app/(app)/{r}", f"clients/web/src/app/(app)/{d}")
        print(f"{d},{core},{api},{cli},{web}")


if __name__ == "__main__":
    main()
