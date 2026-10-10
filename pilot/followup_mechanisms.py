"""Transcript measures behind the follow-ups' mechanism claims (paper Section 7).

  python3 pilot/followup_mechanisms.py   -> data/followup/mechanisms.json

Measures, per wave, model and configuration:
- record size: characters per account of an unfiltered account list, CLI
  `accounts list --json` vs MCP `get_accounts`, small ledger, T2 runs;
- addressing: how L1's account arguments were given (uuid, prefix, code, name,
  or a shell variable whose value the transcript doesn't show);
- tracebacks: runs with a Python traceback in a tool result;
- --balances: runs that used `accounts list --balances`, and how many hit a jq
  error afterwards (the 1322f84 sheet documents its output wrongly);
- discarded write output: composed repetition runs that sent a write's stdout
  to /dev/null (same rule as pilot/oversight.py);
- host reach: commands that used /tmp instead of $TMPDIR, read ~/.claude, ran
  ps, wrote into $HOME, or read the environment;
- failures: data/followup/failure_coding.csv codes each failed follow-up run
  from its final report, quoted there, as a false success, a disclosed failure
  or a consent request.
"""

from __future__ import annotations

import csv
import gzip
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WAVES = {"main": ROOT / "data" / "pilot", "ablation": ROOT / "data" / "pilot-ablation",
         "rewrite": ROOT / "data" / "pilot-v2", "isolation": ROOT / "data" / "pilot-iso"}
UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
WRITE = re.compile(r"\bsalli\s+\S+\s+(?:\S+\s+)?(?:add|post|create|refund)\b")
JQ_ERR = ("Cannot index object", "Cannot iterate over", "jq: error")


def calls(f: Path) -> list[tuple[str, dict, str]]:
    pending, out = {}, []
    for line in gzip.open(f, "rt"):
        try:
            e = json.loads(line)
        except json.JSONDecodeError:
            continue
        m = e.get("message")
        if not isinstance(m, dict) or not isinstance(m.get("content"), list):
            continue
        for b in m["content"]:
            if not isinstance(b, dict):
                continue
            if b.get("type") == "tool_use":
                pending[b["id"]] = (b.get("name") or "", b.get("input") or {})
            elif b.get("type") == "tool_result" and b.get("tool_use_id") in pending:
                c = b.get("content")
                n, i = pending.pop(b["tool_use_id"])
                out.append((n, i, c if isinstance(c, str) else json.dumps(c)))
    return out


def kind(a: str) -> str:
    a = a.strip().strip("'\"")
    if UUID.match(a):
        return "uuid"
    if a.startswith("$") or "{" in a:
        return "variable"
    if a.isdigit():
        return "code"
    if re.fullmatch(r"[0-9a-f][0-9a-f-]{3,34}", a):  # an id's start: 4+ hex characters, possibly past a hyphen
        return "prefix"
    return "name"


def discards(cmd: str) -> bool:
    c = re.sub(r"\s+", "", cmd).replace("2>/dev/null", "")
    return ">/dev/null" in c or "&>/dev/null" in c


def main_tracebacks() -> dict:
    """Main experiment: runs with a Python traceback, by cause, and the longest one.

    The cause is read from the account arguments of the command that raised it:
    a shortened id (prefix), an account code, a shell variable whose value the
    transcript does not show, or none of these.
    """
    d = WAVES["main"]
    runs = {r["run_id"]: r for r in csv.DictReader((d / "runs.csv").open())}
    causes, longest = Counter(), 0
    for rid, r in runs.items():
        kinds, hit = set(), False
        for n, i, t in calls(d / "transcripts" / f"{rid}.jsonl.gz"):
            if "Traceback (most recent call last)" not in t:
                continue
            hit = True
            for m in re.finditer(r"Traceback \(most recent call last\):.*?\n(\w[\w.]*(Error|Exception|Violation)[^\n]*)", t, re.S):
                longest = max(longest, len(m.group(0)))
            args = re.findall(r"--(?:debit|credit)[ =]([^\s:]+):", i.get("command", "")) if n == "Bash" else \
                [x.split(":")[0] for v in i.values() if isinstance(v, list) for x in v if isinstance(x, str)]
            kinds |= {kind(a) for a in args}
        if hit:
            side = "mcp-parity" if r["arm"] == "mcp-parity" else "cli"
            label = next((k for k in ("prefix", "code", "variable") if k in kinds), "other")
            causes[f"{side}/{label}"] += 1
    return {"runs_by_cause": dict(causes), "longest_traceback_chars": longest}


def main() -> None:
    out: dict = {k: defaultdict(dict) for k in
                 ("record_chars_per_account", "addressing_L1", "tracebacks", "balances", "discarded_write_output", "host_reach")}
    for wave, d in WAVES.items():
        if not (d / "runs.csv").exists():
            continue
        runs = {r["run_id"]: r for r in csv.DictReader((d / "runs.csv").open())}
        sizes, addr, tb, tot = defaultdict(list), defaultdict(Counter), Counter(), Counter()
        bal, balerr, disc, rep, reach = Counter(), Counter(), Counter(), Counter(), defaultdict(Counter)
        for rid, r in runs.items():
            f = d / "transcripts" / f"{rid}.jsonl.gz"
            if not f.exists():
                continue
            key = f"{r['model']}/{r['arm']}"
            cs = calls(f)
            tot[key] += 1
            bash = [i.get("command", "") for n, i, _ in cs if n == "Bash"]
            if r["task"] == "T2" and r["size"] == "small":
                for n, i, t in cs:
                    if n.endswith("get_accounts"):
                        sizes["mcp get_accounts"].append(len(t))
                    elif n == "Bash" and re.fullmatch(r"\s*salli accounts list --json\s*", i.get("command", "")):
                        sizes["cli accounts list --json"].append(len(t))
            if r["task"] == "L1":
                for n, i, _t in cs:
                    if n.endswith("post_journal_entry"):
                        for k in ("debit_account_id", "credit_account_id"):
                            if k in i:
                                addr[key][kind(str(i[k]))] += 1
                    elif n == "Bash":
                        for _flag, val in re.findall(r"--(debit|credit)[ =]([^\s]+)", i.get("command", "")):
                            addr[key][kind(val.rsplit(":", 1)[0])] += 1
            if any("Traceback (most recent call last)" in t for _, _, t in cs):
                tb[key] += 1
            used = [k for k, (n, i, _t) in enumerate(cs) if n == "Bash" and "--balances" in i.get("command", "")]
            if used:
                bal[key] += 1
                balerr[key] += any(any(x in t for x in JQ_ERR) for _, _, t in cs[used[0]:])
            if r["task"].startswith("L") and not r["arm"].startswith("mcp") and "pipe" in r["arm"]:
                rep[key] += 1
                disc[key] += any(discards(c) for c in bash if WRITE.search(c))
            txt = "\n".join(bash)
            for label, pat in (("tmp_outside_TMPDIR", r"(?<![\w$])/tmp/(?!claude-)"),
                               # Claude Code saves large outputs under ~/.claude/projects/<run>/.../tool-results
                               # and points the agent to them; reading them is expected. A wildcard over all
                               # projects can also match other sessions' files (it leaked another session's
                               # output into two main-experiment transcripts, since redacted).
                               ("reads_saved_outputs", r"~/\.claude|\$HOME/\.claude|/\.claude/projects|/private/tmp/claude-\d+/"),
                               ("wildcard_across_projects", r"\.claude/projects/\*|/tmp/claude-\d+/\*"),
                               ("lists_processes", r"\bps\s+(aux|-ef|-e|-o|-eo)\b|\bpgrep\b"), ("writes_into_home", r"(>|>>|tee)\s*(~|\$HOME)/(?!\.claude)"),
                               ("reads_environment", r"\benv\b(\s|$)|printenv|\$DATABASE_URL|SERVICE_ROLE")):
                if re.search(pat, txt):
                    reach[label][wave] += 1
        for k, v in sizes.items():
            v = sorted(v)
            out["record_chars_per_account"][wave][k] = {"median_chars": v[len(v) // 2], "n": len(v),
                                                        "per_account": round(v[len(v) // 2] / 16)}
        out["addressing_L1"][wave] = {k: dict(v) for k, v in addr.items()}
        out["tracebacks"][wave] = {k: f"{tb[k]}/{tot[k]}" for k in sorted(tot) if not k.split("/")[1].startswith("mcp")}
        if bal:
            out["balances"][wave] = {k: f"{balerr[k]}/{bal[k]}" for k in sorted(bal)}
        if rep:
            out["discarded_write_output"][wave] = {k: f"{disc[k]}/{rep[k]}" for k in sorted(rep)}
        out["host_reach"][wave] = {label: {"runs": c[wave], "of": len(runs)} for label, c in reach.items()}
    out["main_tracebacks"] = main_tracebacks()
    coding = list(csv.DictReader((ROOT / "data" / "followup" / "failure_coding.csv").open()))
    out["failures"] = dict(Counter((c["wave"], c["outcome"]) for c in coding).items())
    out["failures"] = {f"{w}/{o}": n for (w, o), n in Counter((c["wave"], c["outcome"]) for c in coding).items()}
    (ROOT / "data" / "followup" / "mechanisms.json").write_text(json.dumps(out, indent=1, default=dict) + "\n")
    print(json.dumps(out, indent=1, default=dict)[:4000])


if __name__ == "__main__":
    main()
