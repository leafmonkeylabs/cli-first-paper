# salli CLI reference

Every command prints one JSON document on stdout with --json; messages go to stderr; a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened to a unique prefix. `jq` is available.


### `salli accounts list [options] --json`
List all accounts in the chart of accounts.
Output: `[{id: str, user_id: str, code: str, name: str, type: str, currency: str, parent_id: null, is_active: bool, tax_role: null}, ...]`

### `salli accounts add CODE NAME TYPE [options] --json`
Add an account to the chart of accounts.
Output: `{id: str, code: str, name: str, type: str, currency: str}`

### `salli entry add [options] --json`
Add a balanced journal entry (ACCOUNT_ID:AMOUNT pairs).
Output: `{id: str}`

### `salli ledger trial-balance [options] --json`
Print the trial balance (must net to zero).
Output: `{<account_id>: "<decimal>"}`

### `salli tax compute [options] --json`
Compute income tax using the versioned rules engine.
Output: `{pack_country: str, pack_year: str, pack_version: str, gross_income: "<decimal>", foreign_service_income: "<decimal>", regular_income: "<decimal>", personal_relief_applied: "<decimal>", qp_deduction: "<decimal>", taxable_income: "<decimal>", band_workings: [{...}, ...], fsi_tax: "<decimal>", tax_before_credits: "<decimal>", apit_credit: "<decimal>", ait_credit: "<decimal>", foreign_tax_credit: "<decimal>", total_credits: "<decimal>", tax_payable: "<decimal>", refund_due: "<decimal>", rounding: str}`

### `salli tax packs [options] --json`
List available tax packs.
Output: `[{country: str, year: str, version: str, period_start: str, period_end: str, personal_relief: "<decimal>", bands: [{...}, ...], foreign_service_income: {...}, credits: [str, ...], rounding: str, filing: {...}, qualifying_payment_cap: "<decimal>", qualifying_payment_fraction: "<decimal>"}, ...]`

### `salli reminders add KIND [options] --json`
Create a reminder.
Output: `{id: str, kind: str, due_date: str}`

### `salli profile show [options] --json`
Show the fact-find profile: identity, risk profile, life stage.
Output: `{id: str, email: str, display_name: str, date_of_birth: null, dependents_count: null, employment_status: null, residency_status: str, employer: null, employment_type: null, ird_number: null, risk_score: null, risk_category: null, life_stage: null, mcp_enabled: bool, daily_briefing_enabled: bool, preferred_model: null}`

### `salli budget summary BUDGET_ID [options] --json`
Show category limits vs. actual ledger spend for a budget's period.
Output: JSON (no sample data in the seeded ledger).

### `salli debt payoff-plan [options] --json`
Show the avalanche/snowball payoff plan for all active debts.
Output: `{strategy: str, months_to_payoff: number, total_interest_paid: "<decimal>", schedule: [{...}, ...]}`

### `salli portfolio summary [options] --json`
Show allocation by asset class, total gain/ROI, and rebalancing alerts.
Output: `{total_value: "<decimal>", total_cost_basis: "<decimal>", total_gain: "<decimal>", total_gain_pct: "<decimal>", allocation: [], alerts: []}`

### `salli subscription report SUBSCRIPTION_ID [options] --json`
Show missed-charge/price-change report(s).
Output: JSON (no sample data in the seeded ledger).

### `salli insurance report [options] --json`
Show the coverage-gap report: target vs. actual coverage, missing types,
Output: `{lines: [], missing_types: [], expiring_soon: []}`

### `salli advisor run [options] --json`
Run the Wealth Advisor and generate a fresh report.
Output: the advisor report (runs an LLM; slow).
