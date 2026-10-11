"""Data for the follow-ups figure (paper Figure 5), from the released analysis.

  python3 pilot/followup_figure.py   -> data/followup/fig_<panel>_<series>.csv

Reads data/followup/numbers.json (written by followup_tables.py) and
data/pilot/ratios.csv (written by stats.py); computes nothing new. Each panel
has one row per model and task family, top to bottom: Haiku chains, Haiku
repetition, Sonnet chains, Sonnet repetition. Two series per panel, the first
drawn above the second:
- ablation: the main effect of removing the sheet's options, and of removing
  its output shapes (two-by-two design), relative to the full sheet;
- rewrite: the composed CLI with the sheet relative to its own version's MCP
  server, in the main experiment (0277747, MCP-24) and the rewrite wave
  (1322f84, MCP-46);
- isolation: the same configuration in the isolation wave, relative to MCP-46
  and to MCP-46 serving only the original 24 tools.
Columns: y, ratio, minus, plus (linear offsets of the 95% interval).
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "data" / "followup"
ROWS = [("haiku", "chain"), ("haiku", "loop"), ("sonnet", "chain"), ("sonnet", "loop")]


def write(name: str, series: list[tuple[str, dict]]) -> None:
    """One file per panel and series, data/followup/fig_<panel>_<series>.csv, for pgfplots."""
    for (label, values), off in zip(series, (0.15, -0.15)):
        with (OUT / f"fig_{name}_{label}.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["y", "ratio", "minus", "plus"])
            for i, (m, f) in enumerate(ROWS):
                r = values[(m, f)]
                lo, hi = r.get("lo", r.get("cond_lo")), r.get("hi", r.get("cond_hi"))
                w.writerow([len(ROWS) - 1 - i + off, r["ratio"], round(r["ratio"] - lo, 3), round(hi - r["ratio"], 3)])


def main() -> None:
    n = json.loads((OUT / "numbers.json").read_text())
    main_exp = {(r["model"], r["family"]): {k: float(r[k]) for k in ("ratio", "cond_lo", "cond_hi")}
                for r in csv.DictReader((ROOT / "data" / "pilot" / "ratios.csv").open()) if r["arm"] == "cli-pipe-ref"}
    pick = lambda d, arm="": {(m, f): d[f"{m}/{f}{arm}"] for m, f in ROWS}  # noqa: E731
    fact = n["ablation_factorial"]
    write("ablation", [("options", {(m, f): fact[f"options/{m}/{f}"] for m, f in ROWS}),
                       ("shapes", {(m, f): fact[f"shapes/{m}/{f}"] for m, f in ROWS})])
    write("rewrite", [("main", main_exp), ("rewrite", pick(n["rewrite_vs_mcp"], "/cli-pipe-ref"))])
    iso = n["isolation"]
    write("isolation", [("mcp46", pick(iso["vs_mcp46"], "/cli-pipe-ref")),
                        ("mcp46-24", pick(iso["vs_mcp24_rewritten"], "/cli-pipe-ref"))])
    for f in sorted(OUT.glob("fig_*_*.csv")):
        print(f.name, f.read_text().count("\n") - 1, "rows")


if __name__ == "__main__":
    main()
