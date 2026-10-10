"""Build the CLI reference given to the v2 *-ref arms: the CLI's counterpart of
the v2 MCP server's tool schemas (salli-core 1322f84).

The same rules as pilot/cli_reference.py, applied to the rewritten core:
  - the `salli` commands that do what the MCP tools do (EQUIVALENTS; the MCP
    tools with no counterpart are listed in UNMATCHED, and not in the sheet);
  - for each: usage, arguments and options, from the CLI's own `--help`
    (the TypeScript CLI is a bundled commander program, so its help text is
    its definitions; global options other than --json are left out, as the
    old sheet left out click's --help);
  - the shape of its --json output, taken from running it against a freshly
    seeded, throwaway user through the API server.
New: the old (click) CLI's arguments had no help text, so the old sheet named
them only in the usage line; the new CLI documents each argument, and the sheet
lists them under the usage like the options.

  $SALLI/.venv/bin/python pilot/v2/cli_reference.py > pilot/v2/cli_reference.md
(The API server must be running; see pilot/v2/README.md.)
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from salli_env import CLI_JS, NODE, SERVER, load  # noqa: E402

load()
from seed import make_pat, make_user, revoke_pat  # noqa: E402

# MCP tool -> equivalent CLI command. The old sheet's 14 first, in its order,
# then the tools the rewritten MCP server added, in the server's order.
EQUIVALENTS = [
    ("get_accounts", "accounts list"),
    ("create_account", "accounts add"),
    ("post_journal_entry", "entries add"),
    ("get_trial_balance", "ledger trial-balance"),
    ("get_tax_computation", "tax compute"),
    ("list_tax_packs", "tax packs"),
    ("create_reminder", "reminders add"),
    ("get_financial_profile", "profile get"),
    ("get_budget_summary", "budgets summary"),
    ("get_payoff_plan", "debts payoff-plan"),
    ("get_portfolio_summary", "portfolio summary"),
    ("get_subscription_report", "subscriptions report"),
    ("get_coverage_report", "insurance report"),
    ("run_wealth_advisor", "advisor run"),
    ("get_latest_advisor_report", "advisor latest"),
    ("list_documents", "documents list"),  # and list_memories: --namespace memories
    ("save_document", "documents upload"),  # before show and delete: they use its id
    ("read_document", "documents show"),
    ("delete_document", "documents delete"),
    ("get_cash_flow", "insights cash-flow"),
    ("get_spending", "insights spending"),
    ("get_net_worth_history", "insights net-worth"),
    ("get_recurring_payments", "insights recurring"),
    ("get_cash_forecast", "insights forecast"),
    ("get_safe_to_spend", "insights safe-to-spend"),
    ("get_signals", "insights signals"),
    ("simulate_purchase", "fi simulate-purchase"),
    ("list_pending_transactions", "statements pending"),
    ("categorize_transactions", "statements categorize"),
    ("post_transactions", "statements post"),
    ("discard_transactions", "statements discard"),
    ("suggest_rules", "rules suggest"),
    ("create_rule", "rules add"),
]
ALSO_COVERED = {"list_memories": "documents list"}
# MCP tools with no `salli` command that does the same thing.
UNMATCHED = [
    "explain_tax_band",  # `tax packs` has the bands, but no command explains one band
    "update_document",  # documents can be uploaded, shown and deleted, not edited
    "save_memory", "get_memory",  # memories can be listed, not written or read by slug
    # The user's own tax rule sets (docs/taxrules.md) have no CLI commands yet.
    "get_tax_rule_schema", "list_tax_rule_sets", "get_tax_rule_set", "draft_tax_rule_set",
    "validate_tax_rule_set", "propose_tax_rule_set", "diff_tax_rule_set_versions",
    "evaluate_tax_rule_set",
]
# Example invocations used only to capture output shapes (on a throwaway user).
SAMPLE_ARGS: dict[str, list[str] | None] = {
    "accounts add": ["9990", "Sample", "expense"],
    "entries add": ["--date", "2026-03-01", "--desc", "sample", "--debit", "5000:1", "--credit", "1100:1"],
    "tax compute": ["--year", "2025/26"],
    "reminders add": ["sample", "--due", "2026-04-30"],
    "fi simulate-purchase": ["100000"],
    "documents upload": None,  # a temp file, filled in below
    "documents show": None,  # the uploaded document's id
    "documents delete": None,  # likewise, with --yes
    "rules add": ["Sample", "--if", "description contains sample", "--account", "5000"],
}
# Commands not run: an LLM call, or nothing in a seeded ledger to point them at.
NOT_RUN = {
    "advisor run": "Output: the advisor report (runs an LLM; slow).\n",
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


def cli(args: list[str], env: dict) -> subprocess.CompletedProcess:
    return subprocess.run([NODE, str(CLI_JS), *args], capture_output=True, text=True,
                          env=env, timeout=180)


def run_json(args: list[str], env: dict) -> object:
    out = cli([*args, "--json"], env)
    try:
        return json.loads(out.stdout)
    except json.JSONDecodeError:
        return None


def _sections(text: str) -> dict[str, list[str]]:
    """commander's help, split into its sections, each entry's wrapped lines joined."""
    out: dict[str, list[str]] = {}
    name = "head"
    for line in text.splitlines():
        if re.match(r"^[A-Z][A-Za-z ]*:$", line):
            name = line[:-1]
            out[name] = []
        elif name != "head" and line.startswith("  "):
            if re.match(r"^  \S", line):
                out[name].append(line.strip())
            elif out[name]:
                out[name][-1] += " " + line.strip()
        elif name == "head":
            out.setdefault(name, []).append(line)
    return out


def _pair(entry: str) -> tuple[str, str]:
    parts = re.split(r"\s{2,}", entry, maxsplit=1)
    return parts[0], (parts[1] if len(parts) > 1 else "")


def describe(path: str, env: dict) -> str:
    text = cli([*path.split(), "--help"], env).stdout
    sec = _sections(text)
    usage = next(line for line in sec["head"] if line.startswith("Usage: "))
    doc = next((line.strip() for line in sec["head"][sec["head"].index(usage) + 1:] if line.strip()), "")
    args = []
    for entry in sec.get("Arguments", []):
        name, help_ = _pair(entry)
        args.append(name)
    # Usage: salli statements post [options] <statement> [transactions...]
    tail = usage.split("[options]", 1)[1].split() if "[options]" in usage else []
    shown = [t.strip("<>").upper() if t.startswith("<") else "[" + t.strip("[]").upper() + "]" for t in tail]
    lines = []
    for entry in sec.get("Arguments", []):
        name, help_ = _pair(entry)
        lines.append(f"  {name.upper()}: {help_}")
    for entry in sec.get("Options", []):
        flags, help_ = _pair(entry)
        if flags in ("-h, --help",):
            continue
        flag = flags.split(", ")[-1]
        lines.append(f"  {flag}: {help_}")
    head = f"salli {path} {' '.join(shown)} [options] --json".replace("  ", " ")
    return "\n".join([f"### `{head}`", doc, *lines])


async def main() -> None:
    user = await make_user("small", 1)
    token_id, pat = await make_pat(user)
    cfg = tempfile.mkdtemp(prefix="salli-ref-")
    env = {**os.environ, "SALLI_SERVER": SERVER, "SALLI_TOKEN": pat, "SALLI_CONFIG_DIR": cfg,
           "NO_COLOR": "1"}
    sample = Path(cfg) / "sample.txt"
    sample.write_text("sample\n")
    SAMPLE_ARGS["documents upload"] = [str(sample)]
    print("# salli CLI reference\n")
    print("Every command prints one JSON document on stdout with --json; messages go to stderr; "
          "a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened to a unique prefix. `jq` is available.\n")
    doc_id = None
    for _, path in EQUIVALENTS:
        print(describe(path, env))
        if path in NOT_RUN:
            print(NOT_RUN[path])
            continue
        args = SAMPLE_ARGS.get(path) or []
        if path in ("documents show", "documents delete"):
            args = [doc_id] + (["--yes"] if path == "documents delete" else []) if doc_id else None
        out = run_json(path.split() + args, env) if args is not None else None
        if path == "documents upload" and isinstance(out, dict):
            doc_id = out.get("file_ref") or out.get("id")
        print(f"Output: `{shape(out)}`\n" if out not in (None, [], {}) else "Output: JSON (no sample data in the seeded ledger).\n")
    await revoke_pat(user, token_id)
    print("<!-- MCP tools with no equivalent command: " + ", ".join(UNMATCHED) + "; also covered: "
          + ", ".join(f"{k} by `{v}`" for k, v in ALSO_COVERED.items()) + " -->", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())
