"""Run ledger for the follow-up waves (paper Section 7), with measured concurrency.

  python3 pilot/followup_ledger.py

Every follow-up run attempted was retained; none was discarded or re-collected.
Each run is assigned to its wave by the collection log it appears in. Its
start and end come from <wave>/run_times.csv:
- isolation wave: written by the harness;
- ablation and rewrite waves: derived once from the transcripts'
  modification times on the collecting machine (end) minus the run's wall
  duration (start), and stored, since the harness did not yet record them.
"Concurrent" counts the follow-up runs, from any wave, that were in progress at
a run's midpoint, which is the load on the one machine that ran them.

Also copies the collection logs (and the rewrite's 48-case equivalence check)
into each wave's logs/ folder, with home paths replaced.

Writes data/followup/run_ledger.csv and data/followup/ledger_summary.json.
"""

from __future__ import annotations

import csv
import json
import os
import re
import statistics as st
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WORK = ROOT / "pilot" / "work"
WAVES = [  # (wave, data dir, log file, configured --jobs)
    ("ablation/haiku", "pilot-ablation", "ablation-haiku.log", 6),
    ("rewrite/haiku", "pilot-v2", "v2-haiku.log", 4),
    ("ablation/sonnet", "pilot-ablation", "ablation-sonnet.log", 6),
    ("rewrite/sonnet", "pilot-v2", "v2-sonnet.log", 4),
    ("isolation/haiku", "pilot-iso", "iso-haiku.log", 4),
    ("isolation/sonnet", "pilot-iso", "iso-sonnet.log", 4),
]
EXTRA_LOGS = {"pilot-v2": ["v2-equivalence.log"]}


def iso(t: float) -> str:
    return datetime.fromtimestamp(t, timezone.utc).isoformat(timespec="seconds")


def parse(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def ensure_times(d: Path) -> None:
    """Derive run_times.csv from transcript mtimes once, if the harness didn't write it."""
    f = d / "run_times.csv"
    if f.exists():
        return
    rows = []
    for r in csv.DictReader((d / "runs.csv").open()):
        t = d / "transcripts" / f"{r['run_id']}.jsonl.gz"
        end = os.path.getmtime(t)
        rows.append(f"{r['run_id']},{iso(end - float(r['duration_s']))},{iso(end)},mtime")
    f.write_text("\n".join(rows) + "\n")


def scrub(text: str) -> str:
    home = str(Path.home())
    return text.replace(home, "~").replace(home.replace("/", "-"), "-HOME").replace(Path.home().name, "user")


def main() -> None:
    ledger = []
    for wave, dname, log, jobs in WAVES:
        d = ROOT / "data" / dname
        lp = WORK / log
        if not lp.exists():  # a clean copy has no pilot/work; use the copy shipped with the data
            lp = d / "logs" / log
        if not lp.exists() or not (d / "runs.csv").exists():
            continue
        ensure_times(d)
        times = {}
        for line in (d / "run_times.csv").read_text().splitlines():
            if line.strip():
                rid, s, e, *_ = line.split(",")
                times[rid] = (parse(s), parse(e))
        ids = set(re.findall(r"^([TL]\d-\S+?):", lp.read_text(), re.M))
        runs = {r["run_id"]: r for r in csv.DictReader((d / "runs.csv").open())}
        for rid in sorted(ids & set(runs)):
            r = runs[rid]
            s, e = times[rid]
            ledger.append({"run_id": rid, "wave": wave, "model": r["model"], "arm": r["arm"], "task": r["task"],
                           "size": r["size"], "rep": r["rep"], "success": r["success"], "status": "retained",
                           "configured_jobs": jobs, "started": iso(s), "ended": iso(e), "_s": s, "_e": e})
        (d / "logs").mkdir(exist_ok=True)
        for name in [log, *EXTRA_LOGS.get(dname, [])]:
            if (WORK / name).exists():
                (d / "logs" / name).write_text(scrub((WORK / name).read_text()))
    for x in ledger:
        mid = (x["_s"] + x["_e"]) / 2
        x["concurrent"] = sum(1 for y in ledger if y["_s"] <= mid <= y["_e"])
    summary = {}
    for wave, *_ in WAVES:
        xs = [x for x in ledger if x["wave"] == wave]
        if xs:
            summary[wave] = {"runs": len(xs), "configured_jobs": xs[0]["configured_jobs"],
                             "median_concurrent": st.median(x["concurrent"] for x in xs),
                             "max_concurrent": max(x["concurrent"] for x in xs),
                             "start": iso(min(x["_s"] for x in xs)), "end": iso(max(x["_e"] for x in xs))}
    spans = sorted(summary.items(), key=lambda kv: kv[1]["start"])
    summary["overlaps_min"] = {
        f"{a}|{b}": round(max(0, min(parse(sa["end"]), parse(sb["end"])) - max(parse(sa["start"]), parse(sb["start"]))) / 60)
        for (a, sa), (b, sb) in zip(spans, spans[1:])}
    fields = [k for k in ledger[0] if not k.startswith("_")]
    with (ROOT / "data" / "followup" / "run_ledger.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(ledger)
    (ROOT / "data" / "followup" / "ledger_summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()
