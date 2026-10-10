"""Create a fresh pilot user with a deterministic ledger.

Two sizes vary how much data each read returns:
  small: the 13 starter accounts, 3 debts with liability accounts, ~25 entries
  large: plus 80 expense accounts, 10 more debts, ~430 entries

All entries fall in the 2025/26 year of assessment (Apr 2025 to Mar 2026), so
the tax figures are non-zero.
"""

from __future__ import annotations

import random
import uuid
from datetime import date, timedelta
from decimal import Decimal

from salli_env import services

DEBTS_SMALL = [
    ("Credit Card", 2100, "180000", "0.28", "9000"),
    ("Vehicle Loan", 2200, "2400000", "0.14", "62000"),
    ("Personal Loan", 2300, "650000", "0.19", "21000"),
]
DEBTS_LARGE_EXTRA = [
    ("Store Card", 2400, "95000", "0.31", "6000"),
    ("Housing Loan", 2410, "8200000", "0.11", "98000"),
    ("Education Loan", 2420, "1150000", "0.09", "28000"),
    ("Gold Loan", 2430, "320000", "0.22", "15000"),
    ("Overdraft", 2440, "210000", "0.24", "12000"),
    ("Family Loan", 2450, "500000", "0.00", "10000"),
    ("Leasing Facility", 2460, "1900000", "0.17", "55000"),
    ("Second Credit Card", 2470, "88000", "0.30", "5000"),
    ("Solar Loan", 2480, "640000", "0.13", "18000"),
    ("Appliance Instalment", 2490, "72000", "0.26", "8000"),
]
EXPENSE_NAMES = [
    "Groceries", "Dining Out", "Fuel", "Electricity", "Water", "Mobile", "Internet",
    "Clothing", "Medical", "Pharmacy", "School Fees", "Tuition", "Books", "Gifts",
    "Travel", "Hotels", "Taxis", "Bus and Train", "Parking", "Vehicle Service",
    "Insurance Premiums", "Gym", "Streaming", "Hairdresser", "Household Supplies",
    "Furniture", "Electronics", "Repairs", "Gardening", "Pet Care", "Charity",
    "Temple and Church", "Bank Charges", "Courier", "Stationery", "Kids Activities",
    "Domestic Help", "Laundry", "Cooking Gas", "Coffee",
]


def _d(s: str) -> Decimal:
    return Decimal(s)


async def make_user(size: str, seed: int) -> str:
    assert size in ("small", "large")
    svc = services()
    rng = random.Random(seed)
    user_id = str(uuid.uuid4())
    await svc.profile.ensure_user(user_id, f"pilot-{user_id[:8]}@salli.test", may_create=True)
    await svc.onboarding.complete(
        user_id,
        {"name": "Pilot", "income_sources": ["employment", "freelance", "rental", "interest"]},
    )
    acc = {a.name: a.id for a in await svc.ledger.list_accounts(user_id)}
    cash, bank, equity = acc["Cash"], acc["Bank Account (LKR)"], acc["Opening Equity"]
    salary, freelance, general = (
        acc["Employment Income"],
        acc["Freelance / Business Income"],
        acc["General Expenses"],
    )

    async def entry(day: str, desc: str, dr: str, cr: str, amount: Decimal) -> None:
        await svc.ledger.add_entry(
            user_id, day, desc, "manual",
            [
                {"account_id": dr, "direction": 1, "amount": amount, "currency": "LKR"},
                {"account_id": cr, "direction": -1, "amount": amount, "currency": "LKR"},
            ],
        )

    debts = DEBTS_SMALL + (DEBTS_LARGE_EXTRA if size == "large" else [])
    await entry("2025-04-01", "Opening balance: bank", bank, equity, _d("1250000"))
    await entry("2025-04-01", "Opening balance: cash", cash, equity, _d("40000"))
    for name, code, principal, apr, minimum in debts:
        liab = await svc.ledger.add_account(user_id, str(code), name, "liability")
        await svc.debt.add_debt(
            user_id, {"name": name, "principal": principal, "apr": apr, "minimum_payment": minimum}
        )
        await entry("2025-04-01", f"Opening balance: {name}", equity, liab, _d(principal))

    month = date(2025, 4, 25)
    for _ in range(11):  # Apr 2025 to Feb 2026; March is left for the tasks
        await entry(month.isoformat(), "Salary", bank, salary, _d("350000"))
        month = (month.replace(day=1) + timedelta(days=32)).replace(day=25)
    for day, amt in [("2025-06-10", "120000"), ("2025-09-18", "85000"), ("2026-01-12", "140000")]:
        await entry(day, "Freelance invoice", bank, freelance, _d(amt))
    for m in range(4, 16):
        y, mm = (2025, m) if m <= 12 else (2026, m - 12)
        if (y, mm) > (2026, 2):
            break
        await entry(f"{y}-{mm:02d}-05", "Monthly spending", general, bank, _d("95000"))

    if size == "large":
        expense_ids = []
        for i in range(80):
            name = EXPENSE_NAMES[i % len(EXPENSE_NAMES)] + ("" if i < len(EXPENSE_NAMES) else " (Family)")
            expense_ids.append(await svc.ledger.add_account(user_id, str(5300 + i), name, "expense"))
        start = date(2025, 4, 2)
        for _ in range(400):
            day = start + timedelta(days=rng.randrange(0, 330))
            amt = Decimal(rng.randrange(300, 6000))
            await entry(day.isoformat(), "Card purchase", rng.choice(expense_ids), bank, amt)
    return user_id
