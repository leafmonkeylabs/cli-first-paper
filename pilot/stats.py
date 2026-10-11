"""Statistics for the interface experiment (Section 7 of the paper).

Estimand. For each model, task family (chain or loop) and configuration, the
ratio of cost to the curated MCP configuration (MCP-24). In each cell
(task x ledger size) we take the ratio of geometric-mean costs; cells are
combined by their geometric mean.

Two targets of inference, reported separately:
  * conditional on these tasks: a Welch-type t interval over the runs in each
    cell (Satterthwaite df), and a stratified permutation test of "no
    difference" with Holm correction across all comparisons. A run-level
    bootstrap is kept in ratios.csv (boot_lo/boot_hi) for reference; with
    three to five runs per cell it under-covers;
  * generalising to new tasks like these: a t interval over tasks, using each
    task's log ratio averaged over its two ledger sizes (df = tasks - 1; with
    two loop tasks this interval is very wide, and is reported as such).

Also: the model x configuration interaction, a TOST-style equivalence check
for the one "matches MCP" claim, absolute cost differences, a cold-start
re-pricing, and a sensitivity analysis that puts the superseded shared-tmp
runs back.

Writes to data/pilot/: ratios.csv, per_task.csv, interaction.csv,
sensitivity.csv, success.csv, mechanism.csv, passes.csv, behaviour.csv, forest_*.csv and
the paper's table rows table_{chain,loop,mech,effects}.tex.

  python3 pilot/stats.py
"""

from __future__ import annotations

import csv
import math
import random
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, stdev

sys.path.insert(0, str(Path(__file__).parent))
from analyze import DATA, load  # noqa: E402

B = 5000
P = 10000
SEED = 20261009
ARMS = ["mcp", "mcp-parity", "cli-step", "cli-pipe", "cli-pipe-noskill", "cli-pipe-skills",
        "cli-step-ref", "cli-pipe-ref"]
# Figure 4's rows, top to bottom: the generated server, then the CLI by knowledge.
FOREST_ROWS = ["mcp-parity", "cli-pipe-noskill", "cli-step", "cli-pipe", "cli-pipe-skills", "cli-step-ref", "cli-pipe-ref"]
SHORT = {
    "mcp": "MCP-24", "mcp-parity": "MCP-102", "cli-step": "CLI skill/step",
    "cli-pipe": "CLI skill/comp", "cli-pipe-noskill": "CLI help/comp",
    "cli-pipe-skills": "CLI installed/comp", "cli-step-ref": "CLI sheet/step", "cli-pipe-ref": "CLI sheet/comp",
}
FAMILY = {"T1": "chain", "T2": "chain", "T4": "chain", "T8": "chain", "L1": "loop", "L2": "loop"}
# Two-sided t critical values (0.975 and 0.95 quantiles) by df.
T975 = {1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365}
T95 = {1: 6.314, 2: 2.920, 3: 2.353, 4: 2.132, 5: 2.015, 6: 1.943, 7: 1.895}
# Base input price per token implied by the harness's costs (exact fit; see analyze.py).
PRICE_IN = {"haiku": 0.10e-6, "sonnet": 2.0e-6}
OMEGA_1H, RHO = 2.0, 0.1


def lg(x):
    return math.log(max(x, 1e-9))


def gmean(xs):
    return math.exp(mean(lg(x) for x in xs))


def wilson(s, n, z=1.96):
    p = s / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, running = [0.0] * len(ps), 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (len(ps) - rank) * ps[i]))
        adj[i] = running
    return adj


def cells_for(cell, model, fam, arm):
    keys = sorted({(t, s) for (m, t, s, a) in cell if m == model and FAMILY[t] == fam})
    base = ARMS[0]  # the reference configuration: MCP-24 in the paper
    return [(t, s, cell[(model, t, s, arm)], cell[(model, t, s, base)]) for t, s in keys
            if cell.get((model, t, s, arm)) and cell.get((model, t, s, base))]


def log_ratio(a, b, f=lambda r: r["cost_usd"]):
    return mean(lg(f(r)) for r in a) - mean(lg(f(r)) for r in b)


def t_quantile(p: float, df: float) -> float:
    """Student t quantile by a Cornish-Fisher expansion around the normal
    (accurate to about 1e-3 for df >= 3; exact enough for interval reporting)."""
    from statistics import NormalDist
    z = NormalDist().inv_cdf(p)
    g1 = (z ** 3 + z) / 4
    g2 = (5 * z ** 5 + 16 * z ** 3 + 3 * z) / 96
    g3 = (3 * z ** 7 + 19 * z ** 5 + 17 * z ** 3 - 15 * z) / 384
    g4 = (79 * z ** 9 + 776 * z ** 7 + 1482 * z ** 5 - 1920 * z ** 3 - 945 * z) / 92160
    return z + g1 / df + g2 / df ** 2 + g3 / df ** 3 + g4 / df ** 4


def welch(cs, f=lambda r: r["cost_usd"]):
    """Mean over cells of the difference in mean log cost, with a Welch-type
    standard error and Satterthwaite degrees of freedom. Conditional on the cells."""
    ds, vs, dfs = [], [], []
    for _, _, a, b in cs:
        la, lb = [lg(f(r)) for r in a], [lg(f(r)) for r in b]
        va, vb = stdev(la) ** 2 / len(la), stdev(lb) ** 2 / len(lb)
        ds.append(mean(la) - mean(lb))
        vs.append(va + vb)
        dfs.append((va + vb) ** 2 / ((va ** 2) / (len(la) - 1) + (vb ** 2) / (len(lb) - 1)) if va + vb > 0 else 1e9)
    k = len(cs)
    d = mean(ds)
    se = math.sqrt(sum(vs)) / k
    df = sum(vs) ** 2 / sum(v ** 2 / q for v, q in zip(vs, dfs)) if sum(vs) > 0 else 1e9
    return d, se, df


def cold(r):
    """Cost if the first pass's cache read had been a 1-hour cache write."""
    return r["cost_usd"] + (r["first_cache_read"] or 0) * (OMEGA_1H - RHO) * PRICE_IN[r["model"]]


def analyse(rows, rng, with_tests=True):
    cell = defaultdict(list)
    for r in rows:
        cell[(r["model"], r["task"], r["size"], r["arm"])].append(r)
    out = []
    for model in ("haiku", "sonnet"):
        for fam in ("chain", "loop"):
            for arm in ARMS[1:]:
                cs = cells_for(cell, model, fam, arm)
                if not cs:
                    continue
                lr = [log_ratio(a, b) for _, _, a, b in cs]
                rec = {"model": model, "family": fam, "arm": arm, "ratio": round(math.exp(mean(lr)), 3),
                       "cells": len(cs), "cheaper_cells": sum(x < 0 for x in lr),
                       "runs": sum(len(a) for _, _, a, _ in cs)}
                rec["ratio_cold"] = round(math.exp(mean(log_ratio(a, b, cold) for _, _, a, b in cs)), 3)
                rec["abs_diff_cents"] = round(100 * mean(gmean([r["cost_usd"] for r in a]) -
                                                         gmean([r["cost_usd"] for r in b]) for _, _, a, b in cs), 3)
                if with_tests:
                    # Conditional on these tasks: Welch-type t interval over the
                    # runs in each cell (the run bootstrap is kept for reference;
                    # it under-covers with three to five runs per cell).
                    d, se, df = welch(cs)
                    t975, t95 = t_quantile(0.975, df), t_quantile(0.95, df)
                    rec["cond_lo"], rec["cond_hi"] = round(math.exp(d - t975 * se), 3), round(math.exp(d + t975 * se), 3)
                    rec["cond90_lo"], rec["cond90_hi"] = round(math.exp(d - t95 * se), 3), round(math.exp(d + t95 * se), 3)
                    rec["cond_df"] = round(df, 1)
                    boots = sorted(
                        mean(log_ratio([rng.choice(a) for _ in a], [rng.choice(b) for _ in b]) for _, _, a, b in cs)
                        for _ in range(B))
                    q = lambda p: round(math.exp(boots[min(B - 1, int(p * B))]), 3)  # noqa: E731
                    rec["boot_lo"], rec["boot_hi"] = q(0.025), q(0.975)
                    obs = mean(lr)
                    pools = [([lg(r["cost_usd"]) for r in a] + [lg(r["cost_usd"]) for r in b], len(a))
                             for _, _, a, b in cs]
                    hits = 0
                    for _ in range(P):
                        stat = 0.0
                        for vals, na in pools:
                            v = vals[:]
                            rng.shuffle(v)
                            stat += mean(v[:na]) - mean(v[na:])
                        hits += abs(stat / len(pools)) >= abs(obs) - 1e-12
                    rec["p_perm"] = (hits + 1) / (P + 1)
                    by_task = defaultdict(list)
                    for (t, _, _, _), x in zip(cs, lr):
                        by_task[t].append(x)
                    tl = [mean(v) for v in by_task.values()]
                    rec["tasks"] = len(tl)
                    if len(tl) > 1:
                        se, df = stdev(tl) / math.sqrt(len(tl)), len(tl) - 1
                        rec["task_lo"] = round(math.exp(mean(tl) - T975[df] * se), 3)
                        rec["task_hi"] = round(math.exp(mean(tl) + T975[df] * se), 3)
                        rec["task90_lo"] = round(math.exp(mean(tl) - T95[df] * se), 3)
                        rec["task90_hi"] = round(math.exp(mean(tl) + T95[df] * se), 3)
                        rec["tau"] = round(stdev(tl), 3)
                    rec["per_task"] = {t: round(math.exp(mean(v)), 3) for t, v in by_task.items()}
                out.append(rec)
    if with_tests:
        for r, p in zip(out, holm([r["p_perm"] for r in out])):
            r["p_holm"] = round(p, 4)
            r["p_perm"] = round(r["p_perm"], 4)
    return out, cell


def main() -> None:
    rows = load()
    rng = random.Random(SEED)
    ratios, cell = analyse(rows, rng)

    # Model x configuration interaction (ratio of Sonnet's ratio to Haiku's).
    inter = []
    for fam in ("chain", "loop"):
        for arm in ARMS[1:]:
            ch, cs_ = cells_for(cell, "haiku", fam, arm), cells_for(cell, "sonnet", fam, arm)
            pairs = [(h, s) for h in ch for s in cs_ if h[:2] == s[:2]]
            if not pairs:
                continue
            d = mean(log_ratio(s[2], s[3]) - log_ratio(h[2], h[3]) for h, s in pairs)
            boots = sorted(mean(
                log_ratio([rng.choice(s[2]) for _ in s[2]], [rng.choice(s[3]) for _ in s[3]]) -
                log_ratio([rng.choice(h[2]) for _ in h[2]], [rng.choice(h[3]) for _ in h[3]])
                for h, s in pairs) for _ in range(B))
            row = {"family": fam, "arm": arm, "sonnet_over_haiku": round(math.exp(d), 3),
                   "lo": round(math.exp(boots[int(0.025 * B)]), 3),
                   "hi": round(math.exp(boots[int(0.975 * B) - 1]), 3)}
            for t in sorted({h[0] for h, _ in pairs}):
                tp = [(h, s) for h, s in pairs if h[0] == t]
                row[f"task_{t}"] = round(math.exp(mean(log_ratio(s[2], s[3]) - log_ratio(h[2], h[3]) for h, s in tp)), 3)
            inter.append(row)

    # Sensitivity: superseded shared-tmp originals substituted for their re-runs.
    sens = []
    sup = DATA / "superseded" / "runs_shared_tmp.csv"
    if sup.exists():
        # One key has two superseded runs; the wave-5 run discarded for running
        # beside a smoke test is not an original and is never substituted.
        originals = {(r["task"], r["size"], r["arm"], r["model"], str(r["rep"])): r for r in csv.DictReader(sup.open())
                     if not r["run_id"].endswith("f547bf")}
        alt = []
        for r in rows:
            o = originals.get((r["task"], r["size"], r["arm"], r["model"], str(r["rep"])))
            alt.append({**r, "cost_usd": float(o["cost_usd"])} if o else r)
        alt_ratios, _ = analyse(alt, random.Random(SEED), with_tests=False)
        base = {(x["model"], x["family"], x["arm"]): x for x in ratios}
        for x in alt_ratios:
            b = base[(x["model"], x["family"], x["arm"])]
            sens.append({"model": x["model"], "family": x["family"], "arm": x["arm"], "ratio": b["ratio"],
                         "ratio_with_superseded": x["ratio"], "ratio_cold_start": b["ratio_cold"]})

    success = []
    for model in ("haiku", "sonnet"):
        for arm in ARMS:
            rs = [r for r in rows if r["model"] == model and r["arm"] == arm]
            s = sum(r["success"] for r in rs)
            lo, hi = wilson(s, len(rs))
            success.append({"model": model, "arm": arm, "success": s, "n": len(rs),
                            "rate": round(s / len(rs), 3), "lo": round(lo, 3), "hi": round(hi, 3)})

    mech = []
    for model, task, size in (("sonnet", "T8", "large"), ("haiku", "T8", "large"),
                              ("sonnet", "L2", "large"), ("haiku", "L1", "large")):
        for arm in ARMS:
            rs = cell.get((model, task, size, arm))
            if not rs:
                continue
            f = lambda k: median(r[k] for r in rs)  # noqa: E731
            mech.append({"model": model, "task": task, "size": size, "arm": arm, "n": len(rs),
                         "cache_write": f("cache_write_tokens"), "cache_read": f("cache_read_tokens"),
                         "output": f("output_tokens"), "passes": f("passes"), "calls": f("tool_calls"),
                         "help_calls": f("help_calls"), "result_kchars": round(f("tool_result_chars") / 1000, 1),
                         "cost_cents": round(100 * f("cost_usd"), 2), "seconds": round(f("duration_s"), 1)})
    passes = []
    for model in ("haiku", "sonnet"):
        for arm in ARMS:
            for k in (1, 2, 4, 8):
                rs = [r for r in rows if r["model"] == model and r["arm"] == arm and r["task"] == f"T{k}"]
                if rs:
                    passes.append({"model": model, "arm": arm, "k": k, "passes": median(r["passes"] for r in rs),
                                   "cost_cents": round(100 * median(r["cost_usd"] for r in rs), 2), "n": len(rs)})

    # Behaviour beside cost: median agent-reported seconds per run, tool-result
    # size relative to MCP-24 (geometric mean over cells), and in how many
    # cells the median number of passes was above, below or equal to MCP-24's.
    behaviour = []
    fam_of = lambda t: "chain" if t.startswith("T") else "loop"  # noqa: E731
    for fam in ("chain", "loop"):
        for model in ("haiku", "sonnet", "both"):
            for arm in ARMS:
                rs = [r for r in rows if fam_of(r["task"]) == fam and r["arm"] == arm
                      and model in (r["model"], "both")]
                if not rs:
                    continue
                row = {"family": fam, "model": model, "arm": arm, "runs": len(rs),
                       "median_seconds": round(median(r["duration_s"] for r in rs), 1)}
                if model != "both" and arm != "mcp":
                    keys = [k for k in cell if k[0] == model and fam_of(k[1]) == fam and k[3] == arm]
                    lr, cmp = [], [0, 0, 0]
                    for k in keys:
                        a, b = cell[k], cell[(k[0], k[1], k[2], "mcp")]
                        lr.append(lg(gmean([max(r["tool_result_chars"], 1) for r in a]))
                                  - lg(gmean([max(r["tool_result_chars"], 1) for r in b])))
                        dp = median(r["passes"] for r in a) - median(r["passes"] for r in b)
                        cmp[0 if dp > 0 else 1 if dp < 0 else 2] += 1
                    row.update({"result_chars_ratio": round(math.exp(mean(lr)), 2),
                                "cells_more_passes": cmp[0], "cells_fewer_passes": cmp[1], "cells_same_passes": cmp[2]})
                behaviour.append(row)

    per_task = [{"model": r["model"], "family": r["family"], "arm": r["arm"], "task": t, "ratio": v}
                for r in ratios for t, v in sorted(r["per_task"].items())]
    for r in ratios:
        r.pop("per_task")
    for name, data in (("ratios", ratios), ("per_task", per_task), ("interaction", inter),
                       ("sensitivity", sens), ("success", success), ("mechanism", mech), ("passes", passes),
                       ("behaviour", behaviour)):
        if data:
            fields = list(dict.fromkeys(k for row in data for k in row))
            with (DATA / f"{name}.csv").open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=fields, restval="")
                w.writeheader()
                w.writerows(data)

    # Forest-plot files: conditional (thick) and task-level (thin) intervals,
    # one file per family x model x protocol so the figure can colour by protocol.
    # Both panels share one row per configuration, grouped by knowledge (help,
    # skill, sheet), top to bottom in FOREST_ROWS; a configuration not run on a
    # family has no row in its file. Haiku sits above Sonnet, as in the legend.
    for fam in ("chain", "loop"):
        for model, proto in [(m, p) for m in ("haiku", "sonnet") for p in ("mcp", "cli")]:
            with (DATA / f"forest_{fam}_{model}_{proto}.csv").open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(["y", "ratio", "minus", "plus", "tminus", "tplus", "arm"])
                for i, arm in enumerate(FOREST_ROWS):
                    if (proto == "mcp") != arm.startswith("mcp"):
                        continue
                    x = next((x for x in ratios if x["model"] == model and x["family"] == fam and x["arm"] == arm), None)
                    if x is None:
                        continue
                    off = 0.15 if model == "haiku" else -0.15
                    tlo, thi = max(x.get("task_lo", x["ratio"]), 0.11), min(x.get("task_hi", x["ratio"]), 9.0)
                    w.writerow([len(FOREST_ROWS) - 1 - i + off, x["ratio"], round(x["ratio"] - x["cond_lo"], 3),
                                round(x["cond_hi"] - x["ratio"], 3), round(x["ratio"] - tlo, 3),
                                round(thi - x["ratio"], 3), SHORT[arm]])

    pk = {(x["model"], x["arm"], x["k"]): x for x in passes}
    rr = {(x["model"], x["family"], x["arm"]): x for x in ratios}
    lines = []
    for arm in ARMS:
        cells = []
        for model in ("haiku", "sonnet"):
            if model == "sonnet":
                cells.append("")
            cells += [f"{pk[(model, arm, k)]['cost_cents']:.2f}" for k in (1, 2, 4, 8)]
            r = rr.get((model, "chain", arm))
            cells.append(f"{r['ratio']:.2f}" if r else "1.00")
        lines.append(f"{SHORT[arm]} & " + " & ".join(cells) + r" \\")
    (DATA / "table_chain.tex").write_text("\n".join(lines) + "\n")
    lines = []
    for arm in ARMS:
        if not any(t.startswith("L") for (m, t, s, a) in cell if a == arm):
            continue
        cells = []
        for model in ("haiku", "sonnet"):
            if model == "sonnet":
                cells.append("")
            for t, s in (("L1", "small"), ("L1", "large"), ("L2", "small"), ("L2", "large")):
                cells.append(f"{100 * median(r['cost_usd'] for r in cell[(model, t, s, arm)]):.2f}")
            r = rr.get((model, "loop", arm))
            cells.append(f"{r['ratio']:.2f}" if r else "1.00")
        lines.append(f"{SHORT[arm]} & " + " & ".join(cells) + r" \\")
    (DATA / "table_loop.tex").write_text("\n".join(lines) + "\n")

    m = {(x["model"], x["task"], x["size"], x["arm"]): x for x in mech}
    lines = []
    for (model, task, size), title in ((("sonnet", "T8", "large"), "Sonnet, $k=8$ chain"),
                                       (("sonnet", "L2", "large"), "Sonnet, fan-out to 24")):
        lines.append(rf"\multicolumn{{7}}{{@{{}}l}}{{\textit{{{title}, large ledger}}}} \\")
        for arm in ("mcp", "mcp-parity", "cli-pipe-noskill", "cli-pipe", "cli-pipe-ref"):
            x = m.get((model, task, size, arm))
            if x:
                lines.append(f"{SHORT[arm]} & {x['cache_write'] / 1000:.1f} & {x['cache_read'] / 1000:.1f} & "
                             f"{x['output'] / 1000:.1f} & {x['passes']:g} & {x['calls']:g} & {x['cost_cents']:.1f} \\\\")
    (DATA / "table_mech.tex").write_text("\n".join(lines) + "\n")

    def fmt(x):
        if "task_lo" in x:
            hi = f"{x['task_hi']:.2f}" if x["task_hi"] < 10 else "$>$10"
            lo = f"{x['task_lo']:.2f}" if x["task_lo"] >= 0.1 else "$<$0.1"
            tl = f"{lo}--{hi}"
        else:
            tl = "--"
        p = f"{x['p_holm']:.3f}" if x["p_holm"] >= 0.001 else "$<$.001"
        return f"{x['ratio']:.2f} & {x['cond_lo']:.2f}--{x['cond_hi']:.2f} & {tl} & {p}"
    lines = []
    for fam, title in (("chain", "Chains (4 tasks, 8 cells)"), ("loop", "Repetition (2 tasks, 4 cells)")):
        lines.append(rf"\multicolumn{{10}}{{@{{}}l}}{{\textit{{{title}}}}} \\")
        for arm in ARMS[1:]:
            h, s = rr.get(("haiku", fam, arm)), rr.get(("sonnet", fam, arm))
            if h and s:
                lines.append(f"{SHORT[arm]} & {fmt(h)} & & {fmt(s)} \\\\")
    (DATA / "table_effects.tex").write_text("\n".join(lines) + "\n")

    print(f"{len(rows)} runs")
    for r in ratios:
        print(f"{r['model']:6} {r['family']:5} {r['arm']:17} x{r['ratio']:.2f} cond[{r['cond_lo']:.2f},{r['cond_hi']:.2f}] "
              f"90[{r['cond90_lo']:.2f},{r['cond90_hi']:.2f}] task[{r.get('task_lo', float('nan')):.2f},"
              f"{r.get('task_hi', float('nan')):.2f}] p_holm={r['p_holm']:.4f} cold x{r['ratio_cold']:.2f} "
              f"abs {r['abs_diff_cents']:+.2f}c")
    for x in inter:
        print("interaction", x)
    for x in sens:
        if abs(x["ratio_with_superseded"] - x["ratio"]) > 0.02:
            print("sensitivity", x)


if __name__ == "__main__":
    main()
