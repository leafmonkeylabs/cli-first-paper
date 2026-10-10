"""Build the CLI reference given to the *-ref arms: the CLI's counterpart of
the MCP server's tool schemas.

It covers the CLI commands that do what the MCP tools do (the CLI has no
document or memory store, and no single-band tax explanation, so those MCP
tools have no counterpart here). For each: usage, arguments and options from
the CLI's own definitions, and the shape of its --json output, taken from
running it against a freshly seeded user.

  $SALLI/.venv/bin/python pilot/cli_reference.py > pilot/cli_reference.md
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from salli_env import SALLI, load, salli_env  # noqa: E402

load()
from seed import make_user  # noqa: E402

# MCP tool -> equivalent CLI command
EQUIVALENTS = [
    ("get_accounts", "accounts list"),
    ("create_account", "accounts add"),
    ("post_journal_entry", "entry add"),
    ("get_trial_balance", "ledger trial-balance"),
    ("get_tax_computation", "tax compute"),
    ("list_tax_packs", "tax packs"),
    ("create_reminder", "reminders add"),
    ("get_financial_profile", "profile show"),
    ("get_budget_summary", "budget summary"),
    ("get_payoff_plan", "debt payoff-plan"),
    ("get_portfolio_summary", "portfolio summary"),
    ("get_subscription_report", "subscription report"),
    ("get_coverage_report", "insurance report"),
    ("run_wealth_advisor", "advisor run"),
]
# Example invocations used only to capture output shapes (on a throwaway user).
SAMPLE_ARGS = {
    "accounts add": ["9990", "Sample", "expense"],
    "entry add": None,  # filled in once account ids are known
    "reminders add": ["sample", "--due-date", "2026-04-30"],
}


def shape(v, depth=0, key=""):
    if isinstance(v, dict):
        if depth >= 2 or not v:
            return "{...}" if v else "{}"
        items = list(v.items())
        keys_uuid = all(len(k) == 36 and k.count("-") == 4 for k, _ in items)
        if keys_uuid:
            return "{<account_id>: " + shape(items[0][1], depth + 1, "balance") + "}"
        return "{" + ", ".join(f"{k}: {shape(x, depth + 1, k)}" for k, x in items[:24]) + (", ..." if len(items) > 24 else "") + "}"
    if isinstance(v, list):
        return "[" + shape(v[0], depth + 1) + ", ...]" if v else "[]"
    if isinstance(v, bool):
        return "bool"
    if isinstance(v, (int, float)):
        return "number"
    if v is None:
        return "null"
    s = str(v)
    if key in ("code", "id") or key.endswith("_id"):
        return "str"
    try:
        float(s)
        return '"<decimal>"'
    except ValueError:
        return "str"


def run_json(args: list[str], env: dict) -> object:
    out = subprocess.run([str(SALLI / ".venv" / "bin" / "salli"), *args, "--json"],
                         capture_output=True, text=True, env=env, timeout=120)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def describe(path: str, cmd) -> str:
    args, opts = [], []
    for p in cmd.params:
        if p.name in ("json", "help"):
            continue
        if p.param_type_name == "argument":
            args.append(p.name.upper())
        else:
            flag = max(p.opts, key=len)
            req = " (required)" if p.required else ""
            default = "" if p.required or p.default in (None, False, "", ()) else f" [default: {p.default}]"
            multi = " (repeatable)" if getattr(p, "multiple", False) else ""
            opts.append(f"  {flag}: {(p.help or '').strip()}{req}{multi}{default}")
    head = f"salli {path} {' '.join(args)} [options] --json".replace("  ", " ")
    doc = (cmd.help or "").strip().splitlines()[0] if cmd.help else ""
    return "\n".join([f"### `{head}`", doc, *opts])


async def main() -> None:
    from salli.interfaces.cli.main import cli

    root = cli()
    user = await make_user("small", 1)
    env = {**os.environ, **salli_env(), "SALLI_USER_ID": user}
    accounts = run_json(["accounts", "list"], env)
    cash = next(a["id"] for a in accounts if a["name"] == "Cash")
    exp = next(a["id"] for a in accounts if a["name"] == "General Expenses")
    SAMPLE_ARGS["entry add"] = ["--date", "2026-03-01", "--desc", "sample",
                                "--debit", f"{exp}:1", "--credit", f"{cash}:1"]
    print("# salli CLI reference\n")
    print("Every command prints one JSON document on stdout with --json; messages go to stderr; "
          "a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened "
          "to a unique prefix. `jq` is available.\n")
    for _, path in EQUIVALENTS:
        group, name = path.split()
        cmd = root.commands[group].commands[name]
        print(describe(path, cmd))
        if path == "advisor run":
            print("Output: the advisor report (runs an LLM; slow).\n")
            continue
        out = run_json(path.split() + (SAMPLE_ARGS.get(path) or []), env)
        print(f"Output: `{shape(out)}`\n" if out not in (None, [], {}) else "Output: JSON (no sample data in the seeded ledger).\n")


if __name__ == "__main__":
    asyncio.run(main())
