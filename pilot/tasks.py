"""Pilot tasks and their verifiers.

k is the number of operations in the shortest plan, each needing the state or
output of an earlier one. Every task can be completed through either surface
with salli-core's existing commands and tools. Verifiers read the database
through salli-core's services, never the agent's transcript, except T1, whose
outcome is an answer.
"""

from __future__ import annotations

import re
from decimal import Decimal
from typing import Any

from salli_env import services

YEAR = "2025/26"


def _num(text: str) -> Decimal | None:
    m = re.findall(r"-?\d[\d,]*(?:\.\d+)?", text or "")
    return Decimal(m[-1].replace(",", "")) if m else None


def _nums(text: str) -> list[Decimal]:
    return [Decimal(x.replace(",", "")) for x in re.findall(r"-?\d[\d,]*(?:\.\d+)?", text or "")]


async def _accounts(u: str) -> dict[str, Any]:
    return {a.name: a for a in await services().ledger.list_accounts(u)}


async def _entries_on(u: str, day: str) -> list:
    return await services().ledger.get_entries(u, day, day)


def _is_simple(entry, dr: str, cr: str, amount: Decimal) -> bool:
    deb = [p for p in entry.postings if int(p.direction) == 1]
    cre = [p for p in entry.postings if int(p.direction) == -1]
    return (
        len(deb) == 1 and len(cre) == 1
        and deb[0].account_id == dr and cre[0].account_id == cr
        and Decimal(deb[0].amount) == amount
    )


async def _tax(u: str) -> Decimal:
    return Decimal(str((await services().tax.compute_tax(u, YEAR, persist=False)).tax_payable))


async def _balance(u: str, account_id: str, to: str | None = None) -> Decimal:
    tb = await services().ledger.get_trial_balance(u, None, to)
    return Decimal(tb.get(account_id, 0))


async def _reminders(u: str) -> list[dict]:
    return await services().reminders.list_reminders(u, None)


def _reminder_text(r: dict) -> str:
    return str(r.get("description") or r.get("kind") or "")


# ── Tasks ────────────────────────────────────────────────────────────────────

T1 = (
    "How much income tax do I owe for the 2025/26 year of assessment? "
    "Answer with the amount in LKR."
)

T2 = (
    "I paid LKR 4,250 in cash for groceries on 2026-03-28. "
    "Please record it under my General Expenses account."
)

T4 = (
    "My March salary of LKR 350,000 was paid into my bank account on 2026-03-31. "
    "Please record it as employment income. Then find out how much income tax I owe "
    "for 2025/26 now that it is included, and create a reminder due 2026-05-15 whose "
    "text is exactly 'Set aside LKR <amount> for tax', with that figure as reported by Salli."
)

T8 = (
    "Please do the following, in order.\n"
    "(a) Create an expense account named 'Software Subscriptions' with code 5150.\n"
    "(b) Record LKR 18,600 paid from my bank account on 2026-03-15 for software, "
    "against that new account.\n"
    "(c) Find the expense account, other than General Expenses, with the largest balance "
    "in my trial balance, and record a refund of LKR 12,000 to it on 2026-03-25: money "
    "into my bank account, credited to that expense account.\n"
    "(d) Create a reminder due 2026-04-30 whose text is exactly "
    "'Tax LKR <tax> / Bank LKR <bank>', where <tax> is the income tax I owe for 2025/26 "
    "and <bank> is my bank account's balance after these entries, both as reported by Salli."
)


async def pre_t1(u: str) -> dict:
    return {"tax": await _tax(u)}


async def check_t1(u: str, final: str, pre: dict) -> dict:
    return {"answer": pre["tax"] in _nums(final)}


async def check_t2(u: str, final: str, pre: dict) -> dict:
    acc = await _accounts(u)
    es = await _entries_on(u, "2026-03-28")
    ok = [e for e in es if _is_simple(e, acc["General Expenses"].id, acc["Cash"].id, Decimal(4250))]
    return {"entry": len(ok) == 1, "no_extra_entries": len(es) == len(ok)}


async def check_t4(u: str, final: str, pre: dict) -> dict:
    acc = await _accounts(u)
    bank, salary = acc["Bank Account (LKR)"].id, acc["Employment Income"].id
    es = await _entries_on(u, "2026-03-31")
    entry_ok = sum(_is_simple(e, bank, salary, Decimal(350000)) for e in es) == 1
    tax = await _tax(u)
    rs = [r for r in await _reminders(u) if str(r.get("due_date"))[:10] == "2026-05-15"]
    rem_ok = len(rs) == 1 and _num(_reminder_text(rs[0])) == tax
    return {"entry": entry_ok, "reminder": rem_ok}


async def check_t8(u: str, final: str, pre: dict) -> dict:
    acc = await _accounts(u)
    bank = acc["Bank Account (LKR)"].id
    sw = acc.get("Software Subscriptions")
    out = {"account": bool(sw and sw.code == "5150" and str(sw.type.value if hasattr(sw.type, "value") else sw.type) == "expense")}
    es = await _entries_on(u, "2026-03-15")
    out["software_entry"] = bool(sw) and sum(_is_simple(e, sw.id, bank, Decimal(18600)) for e in es) == 1
    # Expected refund target: largest expense balance before the refund date.
    tb = await services().ledger.get_trial_balance(u, None, "2026-03-24")
    expenses = {a.id: a for a in acc.values() if str(getattr(a.type, "value", a.type)) == "expense" and a.name != "General Expenses"}
    target = max(expenses, key=lambda i: Decimal(tb.get(i, 0)))
    es = await _entries_on(u, "2026-03-25")
    out["refund_entry"] = sum(_is_simple(e, bank, target, Decimal(12000)) for e in es) == 1
    tax, bal = await _tax(u), await _balance(u, bank)
    rs = [r for r in await _reminders(u) if str(r.get("due_date"))[:10] == "2026-04-30"]
    nums = _nums(_reminder_text(rs[0])) if len(rs) == 1 else []
    out["reminder"] = len(nums) >= 2 and nums[-2] == tax and nums[-1] == bal
    out["target"] = expenses[target].name
    return out


async def no_pre(u: str) -> dict:
    return {}


# ── Loop tasks: the same operation over many items ──────────────────────────

_CODES = ["5000", "5100", "5200"]
_DESCS = ["Groceries", "Printer ink", "Plumber", "Fuel", "Client lunch", "Paint", "Pharmacy",
          "Software licence", "Electrician", "Taxi"]
BULK = [
    (f"2026-03-{1 + i:02d}", f"{_DESCS[i % len(_DESCS)]} {i + 1}", 750 + 137 * i,
     _CODES[i % 3], "1100" if i % 2 == 0 else "1200")
    for i in range(25)
]

L1 = (
    "Please record these 25 expenses. Each line is date, description, amount in LKR, the "
    "expense account code to debit, and the account code it was paid from.\n\n"
    + "\n".join(f"{d}, {desc}, {amt}, {dr}, {cr}" for d, desc, amt, dr, cr in BULK)
)

L2 = (
    "For every expense account whose balance in my trial balance is more than LKR 20,000, "
    "create a reminder due 2026-04-30 whose text is exactly 'Review spending: <account name>'."
)


async def check_l1(u: str, final: str, pre: dict) -> dict:
    by_code = {a.code: a.id for a in (await _accounts(u)).values()}
    es = await services().ledger.get_entries(u, "2026-03-01", "2026-03-31")
    found = 0
    for d, _, amt, dr, cr in BULK:
        found += sum(1 for e in es if str(e.entry_date)[:10] == d
                     and _is_simple(e, by_code[dr], by_code[cr], Decimal(amt))) == 1
    return {"entries": found == len(BULK), "no_extra_entries": len(es) == len(BULK), "found": found}


async def pre_l2(u: str) -> dict:
    acc = await _accounts(u)
    tb = await services().ledger.get_trial_balance(u, None, None)
    names = {a.name for a in acc.values()
             if str(getattr(a.type, "value", a.type)) == "expense" and Decimal(tb.get(a.id, 0)) > 20000}
    return {"expected": sorted(f"Review spending: {n}" for n in names)}


async def check_l2(u: str, final: str, pre: dict) -> dict:
    got = sorted(_reminder_text(r) for r in await _reminders(u) if str(r.get("due_date"))[:10] == "2026-04-30")
    return {"reminders": got == pre["expected"], "expected_n": len(pre["expected"]), "got_n": len(got)}


TASKS = {
    "T1": {"k": 1, "prompt": T1, "pre": pre_t1, "check": check_t1},
    "T2": {"k": 2, "prompt": T2, "pre": no_pre, "check": check_t2},
    "T4": {"k": 4, "prompt": T4, "pre": no_pre, "check": check_t4},
    "T8": {"k": 8, "prompt": T8, "pre": no_pre, "check": check_t8},
    # k for loop tasks is the number of writes (L2: 1 on the small ledger, 24 on the large).
    "L1": {"k": 25, "prompt": L1, "pre": no_pre, "check": check_l1},
    "L2": {"k": 0, "prompt": L2, "pre": pre_l2, "check": check_l2},
}
