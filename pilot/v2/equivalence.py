"""Check that each task can be done on the rewritten core through both
surfaces, and that its DB check verifies the same thing (v2: 1322f84).

For every task, on a fresh small user per surface: a scripted correct solution
through the MCP server (over stdio, as the agent sees it) and through the
`salli` CLI (as the agent runs it), then the task's check. Then one deliberate
mistake per task, to see the check fail for the right reason. No agent runs.

  $SALLI/.venv/bin/python pilot/v2/equivalence.py
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from salli_env import CLI_JS, NODE, SALLI, SERVER, load  # noqa: E402

load()
from mcp import ClientSession, StdioServerParameters  # noqa: E402
from mcp.client.stdio import stdio_client  # noqa: E402
from seed import make_pat, make_user, revoke_pat  # noqa: E402
from tasks import BULK, TASKS  # noqa: E402

YEAR = "2025/26"


class Mcp:
    def __init__(self, session: ClientSession) -> None:
        self.s = session

    async def __call__(self, tool: str, **args) -> dict:
        res = await self.s.call_tool(tool, args)
        return json.loads(res.content[0].text)

    async def accounts(self) -> dict:
        return {a["name"]: a for a in (await self("get_accounts"))["accounts"]}


class Cli:
    def __init__(self, env: dict) -> None:
        self.env = env

    def __call__(self, *args: str) -> object:
        out = subprocess.run([NODE, str(CLI_JS), *args, "--json"], capture_output=True,
                             text=True, env=self.env, timeout=120)
        if out.returncode:
            raise RuntimeError(f"salli {' '.join(args)}: exit {out.returncode}: {out.stderr.strip()}")
        return json.loads(out.stdout)

    def accounts(self) -> dict:
        return {a["name"]: a for a in self("accounts", "list")}


# ── Correct solutions, one per surface ──────────────────────────────────────

async def mcp_solve(task: str, m: Mcp, wrong: bool = False) -> str:
    acc = await m.accounts()
    bank, cash = acc["Bank Account (LKR)"]["id"], acc["Cash"]["id"]
    ge, sal = acc["General Expenses"]["id"], acc["Employment Income"]["id"]
    tax = lambda: m("get_tax_computation", year=YEAR)  # noqa: E731
    if task == "T1":
        t = (await tax())["tax_payable"]
        return f"FINAL: LKR {Decimal(t) + (1 if wrong else 0)}"
    if task == "T2":
        await m("post_journal_entry", entry_date="2026-03-28", description="Groceries",
                debit_account_id=ge, credit_account_id=bank if wrong else cash, amount="4250")
        return "FINAL: done"
    if task == "T4":
        await m("post_journal_entry", entry_date="2026-03-31", description="March salary",
                debit_account_id=bank, credit_account_id=sal, amount="350000")
        t = (await tax())["tax_payable"]
        if wrong:  # the tax figure from before the salary was recorded
            t = str(Decimal(t) - Decimal("105000"))
        await m("create_reminder", description=f"Set aside LKR {t} for tax", due_date="2026-05-15")
        return "FINAL: done"
    if task == "T8":
        sw = (await m("create_account", code="5150", name="Software Subscriptions", account_type="expense"))["account_id"]
        await m("post_journal_entry", entry_date="2026-03-15", description="Software",
                debit_account_id=sw, credit_account_id=bank, amount="18600")
        tb = (await m("get_trial_balance"))["trial_balance"]
        exp = [a for a in (await m.accounts()).values() if a["type"] == "expense" and a["name"] != "General Expenses"]
        target = max(exp, key=lambda a: Decimal(tb.get(a["id"], "0")))
        if wrong:  # the smallest instead
            target = min(exp, key=lambda a: Decimal(tb.get(a["id"], "0")))
        await m("post_journal_entry", entry_date="2026-03-25", description="Refund",
                debit_account_id=bank, credit_account_id=target["id"], amount="12000")
        t = (await tax())["tax_payable"]
        b = (await m("get_trial_balance"))["trial_balance"][bank]
        await m("create_reminder", description=f"Tax LKR {t} / Bank LKR {b}", due_date="2026-04-30")
        return "FINAL: done"
    if task == "L1":
        by_code = {a["code"]: a["id"] for a in acc.values()}
        for i, (d, desc, amt, dr, cr) in enumerate(BULK):
            if wrong and i == 7:
                continue  # one line missed
            r = await m("post_journal_entry", entry_date=d, description=desc,
                        debit_account_id=by_code[dr], credit_account_id=by_code[cr], amount=str(amt))
            assert r.get("posted"), r
        return "FINAL: done"
    if task == "L2":
        tb = (await m("get_trial_balance"))["trial_balance"]
        for a in acc.values():
            if a["type"] == "expense" and Decimal(tb.get(a["id"], "0")) > (-1 if wrong else 20000):
                await m("create_reminder", description=f"Review spending: {a['name']}", due_date="2026-04-30")
        return "FINAL: done"
    raise KeyError(task)


def cli_solve(task: str, c: Cli, wrong: bool = False) -> str:
    tax = lambda: c("tax", "compute", "--year", YEAR)["tax_payable"]  # noqa: E731
    if task == "T1":
        return f"FINAL: LKR {Decimal(tax()) + (1 if wrong else 0)}"
    if task == "T2":
        # Accounts by code, as the new CLI allows (the old one needed ids).
        c("entries", "add", "--date", "2026-03-28", "--desc", "Groceries",
          "--debit", "5000:4250", "--credit", ("1200" if wrong else "1100") + ":4250")
        return "FINAL: done"
    if task == "T4":
        c("entries", "add", "--date", "2026-03-31", "--desc", "March salary",
          "--debit", "1200:350000", "--credit", "4100:350000")
        t = tax()
        if wrong:
            t = str(Decimal(t) - Decimal("105000"))
        c("reminders", "add", f"Set aside LKR {t} for tax", "--due", "2026-05-15")
        return "FINAL: done"
    if task == "T8":
        c("accounts", "add", "5150", "Software Subscriptions", "expense")
        c("entries", "add", "--date", "2026-03-15", "--desc", "Software",
          "--debit", "5150:18600", "--credit", "1200:18600")
        tb = c("ledger", "trial-balance")["balances"]
        exp = [a for a in c.accounts().values() if a["type"] == "expense" and a["name"] != "General Expenses"]
        pick = min if wrong else max
        target = pick(exp, key=lambda a: Decimal(tb.get(a["id"], "0")))
        c("entries", "add", "--date", "2026-03-25", "--desc", "Refund",
          "--debit", "1200:12000", "--credit", f"{target['id']}:12000")
        t = tax()
        bank = c.accounts()["Bank Account (LKR)"]["id"]
        b = c("ledger", "trial-balance")["balances"][bank]
        c("reminders", "add", f"Tax LKR {t} / Bank LKR {b}", "--due", "2026-04-30")
        return "FINAL: done"
    if task == "L1":
        for i, (d, desc, amt, dr, cr) in enumerate(BULK):
            if wrong and i == 7:
                continue
            c("entries", "add", "--date", d, "--desc", desc, "--debit", f"{dr}:{amt}", "--credit", f"{cr}:{amt}")
        return "FINAL: done"
    if task == "L2":
        tb = c("ledger", "trial-balance")["balances"]
        for a in c.accounts().values():
            if a["type"] == "expense" and Decimal(tb.get(a["id"], "0")) > (-1 if wrong else 20000):
                c("reminders", "add", f"Review spending: {a['name']}", "--due", "2026-04-30")
        return "FINAL: done"
    raise KeyError(task)


async def one(task: str, surface: str, wrong: bool, size: str) -> dict:
    spec = TASKS[task]
    user = await make_user(size, {"small": 1, "large": 2}[size])
    pre = await spec["pre"](user)
    if surface == "mcp":
        params = StdioServerParameters(command=str(SALLI / ".venv" / "bin" / "python"),
                                       args=[str(HERE / "mcp_stdio.py")],
                                       env={**os.environ, "SALLI_USER_ID": user, "SALLI": str(SALLI)})
        with open(os.devnull, "w") as devnull:
            async with stdio_client(params, errlog=devnull) as (r, w), ClientSession(r, w) as s:
                await s.initialize()
                final = await mcp_solve(task, Mcp(s), wrong)
    else:
        token_id, token = await make_pat(user)
        env = {**os.environ, "SALLI_SERVER": SERVER, "SALLI_TOKEN": token,
               "SALLI_CONFIG_DIR": tempfile.mkdtemp(prefix="salli-eq-")}
        final = await asyncio.to_thread(cli_solve, task, Cli(env), wrong)
        await revoke_pat(user, token_id)
    return await spec["check"](user, final, pre)


async def main() -> None:
    sizes = sys.argv[1:] or ["small"]
    ok = True
    for size in sizes:
        for task in TASKS:
            for surface in ("mcp", "cli"):
                for wrong in (False, True):
                    checks = await one(task, surface, wrong, size)
                    passed = all(v for v in checks.values() if isinstance(v, bool))
                    ok &= passed != wrong
                    print(f"{size:5} {task} {surface:3} {'wrong' if wrong else 'right'}: "
                          f"{'PASS' if passed else 'FAIL'} {json.dumps(checks)}")
    print("all as expected" if ok else "UNEXPECTED RESULTS")


if __name__ == "__main__":
    asyncio.run(main())
