"""Summarise data/pilot/runs.csv.

Writes
  data/pilot/summary.csv   one row per task x size x arm x model
  data/pilot/by_k.csv      medians per k x arm x model (sizes pooled), for the figure
and prints a compact table.

Cost is reported two ways: the harness's dollar figure at list prices, and
input-token equivalents with cache writes weighted 1.25 and cache reads 0.1,
the weights used in the paper's cost model.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import median

DATA = Path(__file__).resolve().parent.parent / "data" / "pilot"
OMEGA, RHO = 1.25, 0.1
ARMS = ["mcp", "cli-step", "cli-pipe", "cli-pipe-noskill", "cli-pipe-skills", "cli-step-ref", "cli-pipe-ref"]


SALLI_CALL = re.compile(r"(?:^|[|;&(`\s])salli\s+(?!--help)")


def shell_metrics(run_id: str) -> dict:
    """From the transcript: Bash calls that read help, that run more than one
    salli command, and that feed salli output into another program."""
    m = {"help_calls": 0, "multi_salli_calls": 0, "piped_calls": 0, "salli_invocations": 0, "skill_loads": 0,
         "agent_duration_s": None, "n_results": 0, "r_input": 0, "r_cache_write": 0, "r_cache_read": 0,
         "r_output": 0, "r_turns": 0, "r_cost": 0.0, "first_cache_read": None}
    path = DATA / "transcripts" / f"{run_id}.jsonl.gz"
    if not path.exists():
        return m
    with gzip.open(path, "rt") as f:
        for line in f:
            try:
                ev = json.loads(line)
            except json.JSONDecodeError:
                continue
            if ev.get("type") == "result":
                # A run can contain several result events: when a command is
                # backgrounded after the harness's 120 s tool limit, its
                # completion re-invokes the agent. Usage and duration are per
                # invocation, so they are summed; total_cost_usd is cumulative.
                u = ev.get("usage", {})
                m["n_results"] += 1
                m["agent_duration_s"] = (m["agent_duration_s"] or 0) + ev.get("duration_ms", 0) / 1000
                m["r_input"] += u.get("input_tokens", 0)
                m["r_cache_write"] += u.get("cache_creation_input_tokens", 0)
                m["r_cache_read"] += u.get("cache_read_input_tokens", 0)
                m["r_output"] += u.get("output_tokens", 0)
                m["r_turns"] += ev.get("num_turns", 0)
                m["r_cost"] = max(m["r_cost"], ev.get("total_cost_usd") or 0)
            if ev.get("type") != "assistant":
                continue
            if m["first_cache_read"] is None:
                m["first_cache_read"] = ev["message"].get("usage", {}).get("cache_read_input_tokens", 0)
            for b in ev["message"].get("content", []):
                if b.get("type") == "tool_use" and b.get("name") == "Skill":
                    m["skill_loads"] += 1
                if b.get("type") != "tool_use" or b.get("name") != "Bash":
                    continue
                cmd = b["input"].get("command", "")
                n = len(SALLI_CALL.findall(" " + cmd))
                m["salli_invocations"] += n
                m["help_calls"] += "--help" in cmd
                m["multi_salli_calls"] += n >= 2
                m["piped_calls"] += bool(re.search(r"salli[^|;&]*--json[^|;&]*\|", cmd) or "$(salli" in cmd)
    return m


def load() -> list[dict]:
    rows = list(csv.DictReader((DATA / "runs.csv").open()))
    for r in rows:
        r.update(shell_metrics(r["run_id"]))
        r["success"] = r["success"] == "True"
        for k in ("k", "passes", "tool_calls", "tool_result_chars", "input_tokens",
                  "cache_write_tokens", "cache_read_tokens", "output_tokens", "num_turns", "denied"):
            r[k] = int(float(r[k] or 0))
        for k in ("cost_usd", "duration_s"):
            r[k] = float(r[k] or 0)
        r["wall_s"] = r["duration_s"]
        if r["agent_duration_s"] is not None:
            r["duration_s"] = r["agent_duration_s"]
        if r["n_results"]:
            # Token columns from all result events (runs.csv kept only the last).
            r["input_tokens"], r["cache_write_tokens"] = r["r_input"], r["r_cache_write"]
            r["cache_read_tokens"], r["output_tokens"] = r["r_cache_read"], r["r_output"]
            r["num_turns"] = r["r_turns"]
            r["cost_usd"] = max(r["cost_usd"], r["r_cost"])
        r["equiv"] = r["input_tokens"] + OMEGA * r["cache_write_tokens"] + RHO * r["cache_read_tokens"]
        r["processed"] = r["input_tokens"] + r["cache_write_tokens"] + r["cache_read_tokens"]
    return rows


def summarise(rows: list[dict], keys: tuple[str, ...]) -> list[dict]:
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in rows:
        groups[tuple(r[k] for k in keys)].append(r)
    out = []
    for key, rs in sorted(groups.items(), key=lambda kv: tuple(str(x) for x in kv[0])):
        out.append({
            **dict(zip(keys, key)),
            "n": len(rs),
            "success": round(sum(r["success"] for r in rs) / len(rs), 2),
            "passes": median(r["passes"] for r in rs),
            "tool_calls": median(r["tool_calls"] for r in rs),
            "help_calls": median(r["help_calls"] for r in rs),
            "piped_calls": round(sum(r["piped_calls"] for r in rs) / len(rs), 2),
            "multi_salli_calls": round(sum(r["multi_salli_calls"] for r in rs) / len(rs), 2),
            "skill_loaded": round(sum(r["skill_loads"] > 0 for r in rs) / len(rs), 2),
            "result_kchars": round(median(r["tool_result_chars"] for r in rs) / 1000, 1),
            "processed_ktok": round(median(r["processed"] for r in rs) / 1000, 1),
            "equiv_ktok": round(median(r["equiv"] for r in rs) / 1000, 1),
            "output_tok": median(r["output_tokens"] for r in rs),
            "cost_usd": round(median(r["cost_usd"] for r in rs), 4),
            "duration_s": round(median(r["duration_s"] for r in rs), 1),
        })
    return out


def write(path: Path, rows: list[dict]) -> None:
    with path.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


ARM_LABEL = {
    "mcp": "MCP tools",
    "cli-step": "CLI, one command per call",
    "cli-pipe": "CLI, composed",
    "cli-pipe-noskill": "CLI, composed, no skill",
    "cli-pipe-skills": "CLI, composed, skills installed",
    "cli-step-ref": "CLI reference, one per call",
    "cli-pipe-ref": "CLI reference, composed",
}


def latex_table(rows: list[dict], byk: list[dict], overall: list[dict]) -> str:
    """Median cost per run (US cents at list prices) by chain depth, plus
    passes at k = 8 and per-run shell behaviour, pooled over ledger sizes."""
    get = {(r["model"], r["arm"], r["k"]): r for r in byk}
    tot = {(r["model"], r["arm"]): r for r in overall}
    lines = []
    for model in ("haiku", "sonnet"):
        n = tot[(model, "mcp")]["n"] // 4
        lines.append(rf"\multicolumn{{8}}{{@{{}}l}}{{\textit{{Claude {model.title()} 5.5, {n} runs per entry}}}} \\")
        for arm in [a for a in ARMS if (model, a) in tot]:
            cents = [f"{100 * get[(model, arm, k)]['cost_usd']:.2f}" for k in (1, 2, 4, 8)]
            t = tot[(model, arm)]
            lines.append(
                f"{ARM_LABEL[arm]} & " + " & ".join(cents)
                + f" & {get[(model, arm, 8)]['passes']:g} & {t['help_calls']:g} & {t['piped_calls']:.1f} \\\\"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    rows = load()
    full = summarise(rows, ("task", "k", "size", "model", "arm"))
    write(DATA / "summary.csv", full)
    byk = summarise(rows, ("model", "arm", "k"))
    write(DATA / "by_k.csv", byk)
    overall = summarise(rows, ("model", "arm"))
    write(DATA / "by_arm.csv", overall)
    (DATA / "table.tex").write_text(latex_table(rows, byk, overall))
    print(f"{len(rows)} runs")
    print(f"{'model':7} {'arm':17} {'k':>2} {'n':>3} {'succ':>5} {'pass':>5} {'calls':>5} {'equiv':>7} {'proc':>7} {'$':>8} {'sec':>6} {'help':>4} {'pipe':>5}")
    for r in byk + [{**o, "k": "*"} for o in overall]:
        print(f"{r['model']:7} {r['arm']:17} {r['k']:>2} {r['n']:>3} {r['success']:>5} {r['passes']:>5} "
              f"{r['tool_calls']:>5} {r['equiv_ktok']:>7} {r['processed_ktok']:>7} {r['cost_usd']:>8} {r['duration_s']:>6} {r['help_calls']:>4} {r['piped_calls']:>5}")


if __name__ == "__main__":
    main()
