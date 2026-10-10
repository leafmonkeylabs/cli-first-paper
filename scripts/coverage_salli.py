"""CLI coverage over time for Salli (Figure 2a and Section 5.2).

Counts, at each sample date (committer date, end of day local time):
  cli_commands       -- `.command(` registrations in src/salli/interfaces/cli/main.py
  api_feature_routes -- @router.get/post/put/patch/delete handlers in
                        src/salli/interfaces/api/routers/*.py, excluding auth.py and
                        mcp_oauth.py (authentication, which no CLI needs)
Usage: python coverage_salli.py --repo ~/Documents/leafmonkeylabs/salli > ../data/salli_coverage.csv
"""
from __future__ import annotations

import argparse
import re
from datetime import date
from pathlib import Path

from _git import commit_before, ls_tree, show

DATES = ["2026-06-18", "2026-06-22", "2026-06-26", "2026-06-30", "2026-07-04", "2026-07-08",
         "2026-07-12", "2026-07-14", "2026-07-15", "2026-07-16", "2026-07-20", "2026-07-25",
         "2026-07-30", "2026-08-05", "2026-08-12", "2026-08-19", "2026-08-26", "2026-09-02",
         "2026-09-09", "2026-09-13"]
START = date(2026, 6, 18)
ROUTE = re.compile(r"@router\.(get|post|put|patch|delete)\b")
EXCLUDED = {"auth.py", "mcp_oauth.py"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--ref", default="HEAD", help="snapshot commit used in the paper")
    args = ap.parse_args()
    repo = args.repo.expanduser()
    print("day,date,commit,cli_commands,api_feature_routes,coverage")
    for d in DATES:
        sha = commit_before(repo, f"{d} 23:59", args.ref)
        if not sha:
            continue
        cli = show(repo, sha, "src/salli/interfaces/cli/main.py").count(".command(")
        api = 0
        for f in ls_tree(repo, sha, "src/salli/interfaces/api/routers/"):
            if Path(f).name in EXCLUDED or not f.endswith(".py"):
                continue
            api += len(ROUTE.findall(show(repo, sha, f)))
        day = (date.fromisoformat(d) - START).days
        cov = f"{cli / api:.2f}" if api else ""
        print(f"{day},{d},{sha[:7]},{cli},{api},{cov}")


if __name__ == "__main__":
    main()
