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

Also the ablation as a 2x2 factorial (options x output shapes), the change
between product versions as a ratio of ratios with a same-commit drift control,
cold-start re-pricing, and the isolation wave (data/pilot-iso).

Writes data/followup/{table_ablation, table_factorial, table_rewrite,
table_isolation}.tex and numbers.json; analyse_wave also rewrites each wave's
ratios_vs_<baseline>.csv.
"""

from __future__ import annotations

import csv
import json
import os
import math
from collections import defaultdict
from pathlib import Path

import followup
import followup_stats as fs
import stats

ROOT = Path(__file__).resolve().parent.parent
ABL, V2, PAPER = ROOT / "data" / "pilot-ablation", ROOT / "data" / "pilot-v2", ROOT / "data" / "pilot"
ISO = ROOT / "data" / "pilot-iso"
ISO_ARMS = ["mcp-24", "cli-pipe-ref", "cli-pipe-ref-ids"]
LABEL_ISO = {"mcp-24": "\\cfg{MCP-46}, 24 tools only", "cli-pipe-ref": "CLI sheet/comp", "cli-pipe-ref-ids": "CLI sheet/comp, ids only"}
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


def _unused_cell_ci(r: dict | None, bold_p: float = 0.05) -> str:
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


def catalogue_share(paper_rows: list[dict]) -> dict:
    """How much of MCP-102's extra cost re-reading its larger catalogue explains.

    The extra prefix is the difference between the configurations' median
    first-pass cache reads. Each pass re-reads it at the cache-read rate (0.1x
    input). Per cell, the share is (extra prefix x MCP-102's mean passes x 0.1
    x input price) / (MCP-102's mean cost - MCP-24's), summarised as the median
    over cells for each model and family. This is a cost-model estimate, not a
    measurement.
    """
    from statistics import median
    fr = {a: median(r["first_cache_read"] for r in paper_rows if r["arm"] == a and r.get("first_cache_read") is not None)
          for a in ("mcp", "mcp-parity")}
    extra = fr["mcp-parity"] - fr["mcp"]
    cells = defaultdict(list)
    for r in paper_rows:
        cells[(r["model"], stats.FAMILY[r["task"]], r["task"], r["size"], r["arm"])].append(r)
    out = defaultdict(list)
    for (m, f, t, sz, a), rs in cells.items():
        if a != "mcp-parity" or (m, f, t, sz, "mcp") not in cells:
            continue
        base = cells[(m, f, t, sz, "mcp")]
        diff = sum(r["cost_usd"] for r in rs) / len(rs) - sum(r["cost_usd"] for r in base) / len(base)
        passes = sum(r["passes"] for r in rs) / len(rs)
        if diff > 0:
            out[(m, f)].append(extra * passes * 0.1 * stats.PRICE_IN[m] / diff)
    return {"extra_prefix_tokens": extra,
            **{f"{m}/{f}": {"median": round(median(v), 2), "min": round(min(v), 2), "max": round(max(v), 2), "cells": len(v)}
               for (m, f), v in out.items()}}


def load_rows(path: Path) -> list[dict]:
    saved = followup.analyze.DATA
    try:
        followup.analyze.DATA = path
        return followup.analyze.load()
    finally:
        followup.analyze.DATA = saved


def ci(r: dict | None, holm_key: str = "p_holm") -> str:
    if not r:
        return "--"
    lo, hi = r.get("cond_lo", r.get("lo")), r.get("cond_hi", r.get("hi"))
    s = f"{r['ratio']:.2f} ({lo:.2f}--{hi:.2f})"
    return f"\\textbf{{{s}}}" if float(r.get(holm_key, 1)) < 0.05 else s


def row4(label: str, get) -> str:
    return f"{label} & {get('haiku','chain')} & {get('haiku','loop')} & & {get('sonnet','chain')} & {get('sonnet','loop')} \\\\"


def row4t(label: str, get) -> str:
    """As row4, with an empty Tokens column (Table 8)."""
    return f"{label} & & {get('haiku','chain')} & {get('haiku','loop')} & & {get('sonnet','chain')} & {get('sonnet','loop')} \\\\"


def main() -> None:
    OUT.mkdir(exist_ok=True)
    abl, abl_rows = followup.analyse_wave(ABL, "cli-pipe-ref", VARIANTS)
    rep, _ = followup.analyse_wave(ABL, "mcp", ["cli-pipe-ref"])
    v2, v2_rows = followup.analyse_wave(V2, "mcp", V2_ARMS)
    paper_rows = load_rows(PAPER)
    paper = key(list(csv.DictReader((PAPER / "ratios.csv").open())))
    for r in paper.values():
        r["ratio"] = float(r["ratio"])
    A, R, V = key(abl), key(rep), key(v2)
    tokens = {r["variant"]: r for r in csv.DictReader((ABL / "sheet_tokens.csv").open())}
    iface = json.loads((V2 / "interface_tokens.json").read_text())
    cA, cAc = fs.log_cells(abl_rows), fs.log_cells(abl_rows, stats.cold)
    cV, cVc = fs.log_cells(v2_rows), fs.log_cells(v2_rows, stats.cold)
    cP = fs.log_cells(paper_rows)
    MF = [(m, f) for m in ("haiku", "sonnet") for f in ("chain", "loop")]

    # Table 8: each sheet variant against the full sheet.
    lines = []
    rr = lambda m, f: ci(R.get((m, f, "cli-pipe-ref")))  # noqa: E731
    lines.append(f"Full sheet vs \\cfg{{MCP-24}} & {int(tokens['full']['tokens']):,} & {rr('haiku','chain')} & {rr('haiku','loop')} & & {rr('sonnet','chain')} & {rr('sonnet','loop')} \\\\")
    lines.append("\\midrule")
    lines.append("Full sheet (reference) & " + f"{int(tokens['full']['tokens']):,}" + " & 1 & 1 & & 1 & 1 \\\\")
    for v in VARIANTS:
        t = tokens[VTOK[v]]
        c = lambda m, f: ci(A.get((m, f, v)))  # noqa: E731
        lines.append(f"{LABEL[v]} & {int(t['tokens']):,} & {c('haiku','chain')} & {c('haiku','loop')} & & {c('sonnet','chain')} & {c('sonnet','loop')} \\\\")
    (OUT / "table_ablation.tex").write_text("\n".join(lines) + "\n")

    # Table: the ablation as a 2x2 factorial (options x output shapes).
    W_OPT = {"cli-pipe-ref-noopts": .5, "cli-pipe-ref": -.5, "cli-pipe-ref-names": .5, "cli-pipe-ref-noout": -.5}
    W_SHP = {"cli-pipe-ref-noout": .5, "cli-pipe-ref": -.5, "cli-pipe-ref-names": .5, "cli-pipe-ref-noopts": -.5}
    W_INT = {"cli-pipe-ref-names": 1, "cli-pipe-ref": 1, "cli-pipe-ref-noout": -1, "cli-pipe-ref-noopts": -1}
    fact = {(name, m, f): fs.contrast(cA, m, f, w) for name, w in (("options", W_OPT), ("shapes", W_SHP)) for m, f in MF}
    fs.holm_apply(list(fact.values()))  # family: the 8 main effects
    inter = {(m, f): fs.contrast(cA, m, f, W_INT) for m, f in MF}
    for r in inter.values():
        r["p_holm"] = r["p"]  # reported unadjusted; not part of the family
    lines = [row4t("Removing the options", lambda m, f: ci(fact[("options", m, f)])),
             row4t("Removing the output shapes", lambda m, f: ci(fact[("shapes", m, f)])),
             row4t("Interaction (both removed)", lambda m, f: ci({**inter[(m, f)], "p_holm": 1}))]
    (OUT / "table_factorial.tex").write_text("\n".join(lines) + "\n")

    # Table 9: the paper's configurations on the rewritten core, with the change itself.
    change = {(m, f, a): fs.cross_wave(cV, cP, m, f, a) for a in V2_ARMS for m, f in MF if (m, f, a) in paper}
    fs.holm_apply(list(change.values()))
    drift = {(m, f): fs.cross_wave(cA, cP, m, f, "cli-pipe-ref") for m, f in MF}
    for r in drift.values():
        r["p_holm"] = 1
    lines = []
    for a in V2_ARMS:
        def c(m, f, a=a):
            old = paper.get((m, f, a))
            o = f"{old['ratio']:.2f}" if old else "--"
            return f"{o} $\\rightarrow$ {ci(V.get((m, f, a)))}"
        lines.append(row4(LABEL_V2[a], c))
        lines.append(row4("\\quad change", lambda m, f, a=a: f"$\\times${ci(change[(m, f, a)])}" if (m, f, a) in change else "--"))
    lines.append("\\midrule")
    lines.append(row4("CLI sheet/comp, \\texttt{0277747} re-run (drift)", lambda m, f: f"$\\times${ci(drift[(m, f)])}"))
    (OUT / "table_rewrite.tex").write_text("\n".join(lines) + "\n")

    # Table: isolation wave (if collected).
    iso = {}
    if (ISO / "runs.csv").exists() and not os.environ.get("SKIP_ISO"):
        iv, iso_rows = followup.analyse_wave(ISO, "mcp", ISO_ARMS)
        i24, _ = followup.analyse_wave(ISO, "mcp-24", ["cli-pipe-ref", "cli-pipe-ref-ids"])
        ia, _ = followup.analyse_wave(ISO, "cli-pipe-ref", ["cli-pipe-ref-ids"])
        I, I24, IA = key(iv), key(i24), key(ia)
        cI = fs.log_cells(iso_rows)
        # The version change split in two: the CLI against an MCP server of the original
        # scope (this wave's mcp-24 vs the main experiment's MCP-24), and MCP's growth.
        cli_side = {(m, f): fs.cross_wave(cI, cP, m, f, "cli-pipe-ref", base="mcp-24", base2="mcp") for m, f in MF}
        fs.holm_apply(list(cli_side.values()))
        lines = ["\\multicolumn{6}{@{}l}{\\textit{Relative to \\cfg{MCP-46}}} \\\\"]
        lines += [row4(LABEL_ISO[a], lambda m, f, a=a: ci(I.get((m, f, a)))) for a in ISO_ARMS]
        lines.append("\\midrule")
        lines.append("\\multicolumn{6}{@{}l}{\\textit{Relative to \\cfg{MCP-46} serving 24 tools}} \\\\")
        lines += [row4(LABEL_ISO[a], lambda m, f, a=a: ci(I24.get((m, f, a)))) for a in ("cli-pipe-ref", "cli-pipe-ref-ids")]
        lines.append("\\midrule")
        lines.append("\\multicolumn{6}{@{}l}{\\textit{Further comparisons}} \\\\")
        lines.append(row4("CLI sheet/comp, ids only $\\div$ codes allowed", lambda m, f: ci(IA.get((m, f, "cli-pipe-ref-ids")))))
        lines.append(row4("CLI sheet/comp $\\div$ 24-tool server: change since \\texttt{0277747}", lambda m, f: f"$\\times${ci(cli_side[(m, f)])}"))
        (OUT / "table_isolation.tex").write_text("\n".join(lines) + "\n")
        iso = {
            "runs": len(iso_rows), "success": sum(r["success"] for r in iso_rows),
            "vs_mcp46": {f"{m}/{f}/{a}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells")} for (m, f, a), r in I.items()},
            "ids_vs_codes": {f"{m}/{f}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm")} for (m, f, _a), r in IA.items()},
            "vs_mcp24_rewritten": {f"{m}/{f}/{a}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells")} for (m, f, a), r in I24.items()},
            "cli_side_change_vs_main": {f"{m}/{f}": r for (m, f), r in cli_side.items()},
            "replicates_rewrite_sheet_comp": {f"{m}/{f}": fs.cross_wave(cI, cV, m, f, "cli-pipe-ref") for m, f in MF},
            "summary": followup.summary(iso_rows),
        }

    # Numbers the prose quotes.
    cp, ca, cv = abs_costs(paper_rows), abs_costs(abl_rows), abs_costs(v2_rows)
    absdiff = {}
    for m, f in MF:
        for a in ("mcp", "cli-pipe-ref"):
            k = (m, f, a)
            absdiff[f"{m}/{f}/{a}"] = {"paper_cents": round(cp[k], 3), "ablation_wave_cents": round(ca[k], 3),
                                       "rewrite_cents": round(cv[k], 3),
                                       "rewrite_vs_paper": round(cv[k] / cp[k], 3),
                                       "ablation_vs_paper": round(ca[k] / cp[k], 3)}
    cold = {}
    for m, f in MF:
        for v in VARIANTS:
            cold[f"ablation/{m}/{f}/{v}"] = fs.contrast(cAc, m, f, {v: 1, "cli-pipe-ref": -1})
        for a in V2_ARMS:
            cold[f"rewrite/{m}/{f}/{a}"] = fs.contrast(cVc, m, f, {a: 1, "mcp": -1})
    numbers = {
        "runs": {"ablation": len(abl_rows), "rewrite": len(v2_rows)},
        "success": {"ablation": sum(r["success"] for r in abl_rows), "rewrite": sum(r["success"] for r in v2_rows)},
        "sheet_tokens": {k: int(v["tokens"]) for k, v in tokens.items()},
        "interface": iface,
        "ablation_vs_full": {f"{m}/{f}/{a}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells")}
                             for (m, f, a), r in A.items()},
        "ablation_factorial": {f"{n}/{m}/{f}": r for (n, m, f), r in fact.items()},
        "ablation_interaction": {f"{m}/{f}": r for (m, f), r in inter.items()},
        "replication_vs_mcp": {f"{m}/{f}": {k: r[k] for k in ("ratio", "cond_lo", "cond_hi", "p_holm")} for (m, f, _a), r in R.items()},
        "rewrite_vs_mcp": {f"{m}/{f}/{a}": {k: r.get(k) for k in ("ratio", "cond_lo", "cond_hi", "p_holm", "cheaper_cells", "cells", "task_lo", "task_hi")}
                           for (m, f, a), r in V.items()},
        "rewrite_change_vs_main": {f"{m}/{f}/{a}": r for (m, f, a), r in change.items()},
        "drift_same_commit": {f"{m}/{f}": r for (m, f), r in drift.items()},
        "cold_start": cold,
        "absolute_cents": absdiff,
        "result_chars_vs_mcp": {"paper_sheet_comp": {f"{m}/{f}": v for (m, f), v in result_ratio(paper_rows, "cli-pipe-ref").items()},
                                "rewrite_sheet_comp": {f"{m}/{f}": v for (m, f), v in result_ratio(v2_rows, "cli-pipe-ref").items()}},
        "isolation": iso,
        "mcp102_catalogue_share": catalogue_share(paper_rows),
        "summary_ablation": followup.summary(abl_rows),
        "summary_rewrite": followup.summary(v2_rows),
    }
    (OUT / "numbers.json").write_text(json.dumps(numbers, indent=1) + "\n")
    for name in ("table_ablation", "table_factorial", "table_rewrite", "table_isolation"):
        if (OUT / f"{name}.tex").exists():
            print(f"--- {name}\n" + (OUT / f"{name}.tex").read_text())


def _paper_row(r: dict) -> dict:
    return {**r, "cost_usd": float(r["cost_usd"]), "tool_result_chars": int(float(r["tool_result_chars"] or 0))}


if __name__ == "__main__":
    main()
