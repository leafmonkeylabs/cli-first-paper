"""Analyse a follow-up wave with the paper's statistics, unchanged.

  python3 pilot/followup.py <data-dir> <baseline-arm> <arm> [<arm> ...]

Runs stats.analyse (geometric-mean cost ratio per cell, Welch interval over
runs, stratified permutation test, Holm over the comparisons in this call)
with <baseline-arm> as the reference, and writes
<data-dir>/ratios_vs_<baseline>.csv plus a success and behaviour summary
(<data-dir>/summary_followup.csv). Nothing under data/pilot is touched.

Waves:
  data/pilot-ablation   command-sheet ablation on salli-core 0277747 (agenda S3)
                        baselines: mcp, and cli-pipe-ref (the full sheet)
  data/pilot-v2         the paper's tasks on the rewritten salli-core (1322f84)
"""

from __future__ import annotations

import csv
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import median

sys.path.insert(0, str(Path(__file__).parent))
import analyze  # noqa: E402
import stats  # noqa: E402


def analyse_wave(data: Path, base: str, arms: list[str], write: bool = True) -> tuple[list[dict], list[dict]]:
    """The paper's statistics on one follow-up wave, against <base>."""
    saved = analyze.DATA, stats.ARMS
    try:
        analyze.DATA = data
        rows = analyze.load()
        stats.ARMS = [base, *arms]
        ratios, _ = stats.analyse(rows, random.Random(stats.SEED))
    finally:
        # Restore the modules' globals so later callers see the paper's settings.
        analyze.DATA, stats.ARMS = saved
    for r in ratios:
        r.pop("per_task", None)
    if write:
        fields = list(dict.fromkeys(k for r in ratios for k in r))
        with (data / f"ratios_vs_{base}.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields, restval="")
            w.writeheader()
            w.writerows(ratios)
    return ratios, rows


def summary(rows: list[dict]) -> list[dict]:
    by = defaultdict(list)
    for r in rows:
        by[(r["model"], stats.FAMILY[r["task"]], r["arm"])].append(r)
    return [{"model": model, "family": fam, "arm": arm, "runs": len(rs),
             "success": sum(r["success"] for r in rs),
             "median_cents": round(100 * median(r["cost_usd"] for r in rs), 3),
             "median_passes": median(r["passes"] for r in rs),
             "median_calls": median(r["tool_calls"] for r in rs),
             "median_help_calls": median(r.get("help_calls", 0) for r in rs),
             "median_result_kchars": round(median(r["tool_result_chars"] for r in rs) / 1000, 1),
             "median_seconds": round(median(r["duration_s"] for r in rs), 1)}
            for (model, fam, arm), rs in sorted(by.items())]


def main() -> None:
    data, base, arms = Path(sys.argv[1]).resolve(), sys.argv[2], sys.argv[3:]
    ratios, rows = analyse_wave(data, base, arms)
    print(f"cost relative to {base} (Welch 95% CI over runs; Holm over {len(ratios)} comparisons)")
    for r in ratios:
        print(f"  {r['model']:6} {r['family']:5} {r['arm']:22} {r['ratio']:.3f} "
              f"[{r['cond_lo']:.3f}, {r['cond_hi']:.3f}]  p_holm={r['p_holm']}  cheaper {r['cheaper_cells']}/{r['cells']}")
    summ = summary(rows)
    with (data / "summary_followup.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(summ[0]))
        w.writeheader()
        w.writerows(summ)


if __name__ == "__main__":
    main()
