"""Build the run ledger: every run attempted, the wave that collected it, and
what became of it.

Waves (in order; each was started after the previous one's results were seen):
  1  pilot-*.log   MCP-24, CLI skill/step, skill/comp, help/comp; chains only. 6 parallel.
                   Composed arms under a Claude Code allowlist (later superseded).
  2  pilot2-*.log  CLI sheet/step and sheet/comp added; composed arms re-collected
                   with permissions bypassed under deny-list v1 (interpreters denied). 8 parallel.
  3  pilot3-*.log  CLI installed/comp. 8 parallel. Deny-list v1. Its loop runs superseded.
  4  pilot4.log    MCP-102 on chains; loop tasks for six arms. 8 parallel. Deny-list v2
                   (interpreters allowed; only salli added to PATH); shared temp dir.
  5  pilot5.log    Composed runs that used a shared temp path, re-collected one at a time
                   with a temp dir per run. Deny-list v2.

Writes data/pilot/run_ledger.csv and copies the logs to data/pilot/logs/. Without
pilot/work/ (a fresh clone), it reads the copies already in data/pilot/logs/.

  python3 pilot/ledger.py
"""

from __future__ import annotations

import csv
import re
import shutil
from pathlib import Path

HERE = Path(__file__).parent
DATA = HERE.parent / "data" / "pilot"
LOGS = [
    ("pilot-haiku.log", 1, 6), ("pilot-sonnet.log", 1, 6),
    ("pilot2-haiku.log", 2, 8), ("pilot2-sonnet.log", 2, 8),
    ("pilot3-haiku.log", 3, 8), ("pilot3-sonnet.log", 3, 8),
    ("pilot4.log", 4, 8), ("pilot5.log", 5, 1),
]
COMPOSED = {"cli-pipe", "cli-pipe-noskill", "cli-pipe-ref", "cli-pipe-skills"}
SUPERSEDED = {
    "runs_allowlist_composed.csv": "allowlist could not check composed commands",
    "runs_loop_denylist_v1.csv": "deny-list v1 refused interpreters on loop tasks",
    "runs_shared_tmp.csv": "shared temp dir between parallel runs",
    "runs_operator_stopped.csv": "stopped by the operator in error",
}
NOTES = {
    "T8-large-cli-pipe-noskill-haiku-1-f547bf": "collected in wave 5 while a smoke test ran in parallel and wrote "
                                                "to /tmp; discarded before analysis and re-collected",
    "L2-large-cli-pipe-sonnet-1-e6305b": "exceeded the 900 s read timeout with no output; re-collected as 61bdae",
    "L2-large-cli-pipe-sonnet-1-61bdae": "re-collection of e6305b, run alone outside the logged waves but with "
                                         "wave 4's shared temp path; superseded with the other shared-temp runs",
}


def permissions(arm: str, wave: int) -> str:
    if arm in ("mcp", "mcp-parity"):
        return "mcp tools only"
    if arm not in COMPOSED:
        return "allowlist: salli only"
    return {1: "allowlist (superseded)", 2: "deny-list v1", 3: "deny-list v1"}.get(wave, "deny-list v2")


def main() -> None:
    wave_of, par_of = {}, {}
    (DATA / "logs").mkdir(parents=True, exist_ok=True)
    for name, wave, par in LOGS:
        path = HERE / "work" / name
        if path.exists():
            text = path.read_text().replace(str(Path.home()), "~").replace(Path.home().name, "user")
            (DATA / "logs" / name).write_text(text)
        elif (DATA / "logs" / name).exists():
            text = (DATA / "logs" / name).read_text()
        else:
            continue
        for rid in re.findall(r"^([TL]\d-(?:small|large)-[\w-]+-(?:haiku|sonnet)-\d-[0-9a-f]{6}):", text, re.M):
            wave_of.setdefault(rid, wave)
            par_of.setdefault(rid, par)
    ledger = []
    retained = list(csv.DictReader((DATA / "runs.csv").open()))
    for r in retained:
        rid = r["run_id"]
        w = wave_of.get(rid, "")
        ledger.append({"run_id": rid, "task": r["task"], "size": r["size"], "arm": r["arm"], "model": r["model"],
                       "rep": r["rep"], "wave": w, "parallel": par_of.get(rid, ""),
                       "permissions": permissions(r["arm"], w or 5), "status": "retained", "reason": ""})
    for fname, reason in SUPERSEDED.items():
        f = DATA / "superseded" / fname
        if not f.exists():
            continue
        for r in csv.DictReader(f.open()):
            rid = r["run_id"]
            w = wave_of.get(rid, "")
            ledger.append({"run_id": rid, "task": r["task"], "size": r["size"], "arm": r["arm"], "model": r["model"],
                           "rep": r["rep"], "wave": w, "parallel": par_of.get(rid, ""),
                           "permissions": permissions(r["arm"], w or 5), "status": "superseded",
                           "reason": NOTES.get(rid, reason)})
    for rid, note in NOTES.items():
        if not any(x["run_id"] == rid for x in ledger):
            ledger.append({"run_id": rid, "task": rid[:2], "size": rid.split("-")[1], "arm": "", "model": "",
                           "rep": "", "wave": wave_of.get(rid, ""), "parallel": par_of.get(rid, ""),
                           "permissions": "", "status": "superseded", "reason": note})
    with (DATA / "run_ledger.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ledger[0]))
        w.writeheader()
        w.writerows(ledger)
    from collections import Counter
    print(len(ledger), "runs in ledger;", Counter((x["status"], x["wave"]) for x in ledger))


if __name__ == "__main__":
    main()
