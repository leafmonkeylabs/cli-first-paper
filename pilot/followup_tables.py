"""Every number and table in the paper's follow-up section (Section 7).

  python3 pilot/followup_tables.py

Uses the paper's statistics (followup.analyse_wave, which runs stats.analyse):
  1. ablation: each sheet variant against the full sheet. Holm over the 16
     comparisons (4 variants x 2 families x 2 models).
  2. ablation replication: the full sheet against MCP-24, re-run in the same
     wave. Holm over 4.
  3. rewritten core: four CLI configurations against its MCP server. Holm over 16.
Also the absolute costs (geometric mean over cells of each cell's geometric
mean cost) for the paper, the ablation wave and the rewritten core; the size of
tool results relative to MCP; and success counts.

Writes data/followup/{table_ablation.tex, table_rewrite.tex, numbers.json}.
"""

from __future__ import annotations

import csv
import json
import math
from collections import defaultdict
from pathlib import Path

import followup
import stats

ROOT = Path(__file__).resolve().parent.parent
ABL, V2, PAPER = ROOT / "data" / "pilot-ablation", ROOT / "data" / "pilot-v2", ROOT / "data" / "pilot"
OUT = ROOT / "data" / "followup"
VARIANTS = ["cli-pipe-ref-noout", "cli-pipe-ref-noopts", "cli-pipe-ref-names", "cli-pipe-ref-wide"]
V2_ARMS = ["cli-pipe-noskill", "cli-pipe", "cli-step-ref", "cli-pipe-ref"]
LABEL = {"cli-pipe-ref": "Full sheet", "cli-pipe-ref-noout": "No output shapes",
         "cli-pipe-ref-noopts": "No options", "cli-pipe-ref-names": "Names only",
         "cli-pipe-ref-wide": "Every command", "cli-pipe-noskill": "CLI help/comp",
         "cli-pipe": "CLI skill/comp", "cli-step-ref": "CLI sheet/step"}
VTOK = {"cli-pipe-ref": "full", "cli-pipe-ref-noout": "noout", "cli-pipe-ref-noopts": "noopts",
        "cli-pipe-ref-names": "names", "cli-pipe-ref-wide": "wide"}
LABEL_V2 = {**LABEL, "cli-pipe-ref": "CLI sheet/comp"}


def key(rs: list[dict]) -> dict:
    return {(r["model"], r["family"], r["arm"]): r for r in rs}


def cell_ci(r: dict | None, bold_p: float = 0.05) -> str:
    if not r:
        return "--"
    s = f"{r['ratio']:.2f} ({r['cond_lo']:.2f}--{r['cond_hi']:.2f})"
    return f"\\textbf{{{s}}}" if float(r["p_holm"]) < bold_p else s


def abs_costs(rows: list[dict]) -> dict:
    cells = defaultdict(list)
    for r in rows:
        cells[(r["model"], stats.FAMILY[r["task"]], r["task"], r["size"], r["arm"])].append(r["cost_usd"])
    fam = defaultdict(list)
    for (m, f, _t, _s, a), xs in cells.items():
        fam[(m, f, a)].append(sum(math.log(x) for x in xs) / len(xs))
    return {k: math.exp(sum(v) / len(v)) * 100 for k, v in fam.items()}


def result_ratio(rows: list[dict], arm: str) -> dict:
    """Tool-result characters of <arm> relative to MCP, geometric mean over cells."""
    cells = defaultdict(list)
    for r in rows:
        cells[(r["model"], stats.FAMILY[r["task"]], r["task"], r["size"], r["arm"])].append(max(r["tool_result_chars"], 1))
    gm = {k: math.exp(sum(math.log(x) for x in v) / len(v)) for k, v in cells.items()}
    out = defaultdict(list)
    for (m, f, t, s, a), v in gm.items():
        if a == arm and (m, f, t, s, "mcp") in gm:
            out[(m, f)].append(math.log(v / gm[(m, f, t, s, "mcp")]))
    return {k: round(math.exp(sum(v) / len(v)), 2) for k, v in out.items()}


def main() -> None:
    OUT.mkdir(exist_ok=True)
    abl, abl_rows = followup.analyse_wave(ABL, "cli-pipe-ref", VARIANTS)
    rep, _ = followup.analyse_wave(ABL, "mcp", ["cli-pipe-ref"])
    v2, v2_rows = followup.analyse_wave(V2, "mcp", V2_ARMS)
    paper = key(list(csv.DictReader((PAPER / "ratios.csv").open())))
    for r in paper.values():
        r["ratio"] = float(r["ratio"])
    A, R, V = key(abl), key(rep), key(v2)
    tokens = {r["variant"]: r for r in csv.DictReader((ABL / "sheet_tokens.csv").open())}
    iface = json.loads((V2 / "interface_tokens.json").read_text())

    # Table: sheet ablation.
    lines = []
    rr = lambda m, f: cell_ci(R.get((m, f, "cli-pipe-ref")))  # noqa: E731
    lines.append(f"Full sheet vs \\cfg{{MCP-24}} & {int(tokens['full']['tokens']):,} & {rr('haiku','chain')} & {rr('haiku','loop')} & & {rr('sonnet','chain')} & {rr('sonnet','loop')} \\\\")
    lines.append("\\midrule")
    lines.append("Full sheet (reference) & " + f"{int(tokens['full']['tokens']):,}" + " & 1 & 1 & & 1 & 1 \\\\")
    for v in VARIANTS:
        t = tokens[VTOK[v]]
        c = lambda m, f: cell_ci(A.get((m, f, v)))  # noqa: E731
        lines.append(f"{LABEL[v]} & {int(t['tokens']):,} & {c('haiku','chain')} & {c('haiku','loop')} & & {c('sonnet','chain')} & {c('sonnet','loop')} \\\\")
    (OUT / "table_ablation.tex").write_text("\n".join(lines) + "\n")

    # Table: the paper's configurations on the rewritten core.
    lines = []
    for a in V2_ARMS:
        def c(m, f):
            old = paper.get((m, f, a))
            new = V.get((m, f, a))
            o = f"{old['ratio']:.2f}" if old else "--"
            return f"{o} $\\rightarrow$ {cell_ci(new)}"
        lines.append(f"{LABEL_V2[a]} & {c('haiku','chain')} & {c('haiku','loop')} & & {c('sonnet','chain')} & {c('sonnet','loop')} \\\\")
    (OUT / "table_rewrite.tex").write_text("\n".join(lines) + "\n")

    # Numbers the prose quotes.
    cp, ca, cv = abs_costs([*map(_paper_row, csv.DictReader((PAPER / "runs.csv").open()))]), abs_costs(abl_rows), abs_costs(v2_rows)
    absdiff = {}
    for m in ("haiku", "sonnet"):
        for f in ("chain", "loop"):
            for a in ("mcp", "cli-pipe-ref"):
                k = (m, f, a)
                absdiff[f"{m}/{f}/{a}"] = {"paper_cents": round(cp[k], 3), "ablation_wave_cents": round(ca[k], 3),
                                           "rewrite_cents": round(cv[k], 3),
                                           "rewrite_vs_paper": round(cv[k] / cp[k], 3),
                                           "ablation_vs_paper": round(ca[k] / cp[k], 3)}
    numbers = {
        "runs": {"ablation": len(abl_rows), "rewrite": len(v2_rows)},
        "success": {"ablation": sum(r["success"] for r in abl_rows), "rewrite": sum(r["success"] for r in v2_rows)},
        "sheet_tokens": {k: int(v["tokens"]) for k, v in tokens.items()},
        "interface": iface,
        "ablation_vs_full": {f"{m}/{f}/{a}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells")}
                             for (m, f, a), r in A.items()},
        "replication_vs_mcp": {f"{m}/{f}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm")} for (m, f, _a), r in R.items()},
        "rewrite_vs_mcp": {f"{m}/{f}/{a}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells")}
                           for (m, f, a), r in V.items()},
        "absolute_cents": absdiff,
        "result_chars_vs_mcp": {"paper_sheet_comp": {f"{m}/{f}": v for (m, f), v in result_ratio([*map(_paper_row, csv.DictReader((PAPER / "runs.csv").open()))], "cli-pipe-ref").items()},
                                "rewrite_sheet_comp": {f"{m}/{f}": v for (m, f), v in result_ratio(v2_rows, "cli-pipe-ref").items()}},
        "summary_ablation": followup.summary(abl_rows),
        "summary_rewrite": followup.summary(v2_rows),
    }
    (OUT / "numbers.json").write_text(json.dumps(numbers, indent=1) + "\n")
    print((OUT / "table_ablation.tex").read_text())
    print((OUT / "table_rewrite.tex").read_text())


def _paper_row(r: dict) -> dict:
    return {**r, "cost_usd": float(r["cost_usd"]), "tool_result_chars": int(float(r["tool_result_chars"] or 0))}


if __name__ == "__main__":
    main()
