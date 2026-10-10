# salli CLI reference

Every command prints one JSON document on stdout with --json; messages go to stderr; a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened to a unique prefix. `jq` is available.

### `salli accounts list [options] --json`
List all accounts in the chart of accounts.
Output: `[{id: str, user_id: str, code: str, name: str, type: str, currency: str, parent_id: null, is_active: bool, tax_role: null}, ...]`

### `salli accounts add CODE NAME TYPE [options] --json`
Add an account to the chart of accounts.
  --currency: ISO currency code [default: LKR]
Output: `{id: str, code: str, name: str, type: str, currency: str}`

### `salli entry add [options] --json`
Add a balanced journal entry (ACCOUNT_ID:AMOUNT pairs).
  --date: YYYY-MM-DD (required)
  --desc: Description (required)
  --debit: ACCOUNT_ID:AMOUNT (repeat for splits) (required) (repeatable)
  --credit: ACCOUNT_ID:AMOUNT (repeat for splits) (required) (repeatable)
  --receipt: Document ID of an attached receipt/file (source stays 'manual')
Output: `{id: str}`

### `salli ledger trial-balance [options] --json`
Print the trial balance (must net to zero).
  --from: YYYY-MM-DD
  --to: YYYY-MM-DD
Output: `{<account_id>: "<decimal>"}`

### `salli tax compute [options] --json`
Compute income tax using the versioned rules engine.
  --year: Year of assessment [default: 2025/26]
Output: `{pack_country: str, pack_year: str, pack_version: str, gross_income: "<decimal>", foreign_service_income: "<decimal>", regular_income: "<decimal>", personal_relief_applied: "<decimal>", qp_deduction: "<decimal>", taxable_income: "<decimal>", band_workings: [{...}, ...], fsi_tax: "<decimal>", tax_before_credits: "<decimal>", apit_credit: "<decimal>", ait_credit: "<decimal>", foreign_tax_credit: "<decimal>", total_credits: "<decimal>", tax_payable: "<decimal>", refund_due: "<decimal>", rounding: str}`

### `salli tax packs [options] --json`
List available tax packs.
Output: `[{country: str, year: str, version: str, period_start: str, period_end: str, personal_relief: "<decimal>", bands: [{...}, ...], foreign_service_income: {...}, credits: [str, ...], rounding: str, filing: {...}, qualifying_payment_cap: "<decimal>", qualifying_payment_fraction: "<decimal>"}, ...]`

### `salli reminders add KIND [options] --json`
Create a reminder.
  --due-date: YYYY-MM-DD (required)
Output: `{id: str, kind: str, due_date: str}`

### `salli profile show [options] --json`
Show the fact-find profile: identity, risk profile, life stage.
Output: `{id: str, email: str, display_name: str, date_of_birth: null, dependents_count: null, employment_status: null, residency_status: str, employer: null, employment_type: null, ird_number: null, risk_score: null, risk_category: null, life_stage: null, mcp_enabled: bool, daily_briefing_enabled: bool, preferred_model: null}`

### `salli budget summary BUDGET_ID [options] --json`
Show category limits vs. actual ledger spend for a budget's period.
Output: JSON (no sample data in the seeded ledger).

### `salli debt payoff-plan [options] --json`
Show the avalanche/snowball payoff plan for all active debts.
  --extra: Extra monthly payment [default: 0]
  --strategy: avalanche (highest APR first) or snowball (smallest balance first) [default: avalanche]
Output: `{strategy: str, months_to_payoff: number, total_interest_paid: "<decimal>", schedule: [{...}, ...]}`

### `salli portfolio summary [options] --json`
Show allocation by asset class, total gain/ROI, and rebalancing alerts.
  --target: ASSET_CLASS:FRACTION, e.g. equity:0.7 (repeat); omit to skip rebalancing alerts (repeatable) [default: []]
Output: `{total_value: "<decimal>", total_cost_basis: "<decimal>", total_gain: "<decimal>", total_gain_pct: "<decimal>", allocation: [], alerts: []}`

### `salli subscription report SUBSCRIPTION_ID [options] --json`
Show missed-charge/price-change report(s).
Output: JSON (no sample data in the seeded ledger).

### `salli insurance report [options] --json`
Show the coverage-gap report: target vs. actual coverage, missing types,
Output: `{lines: [], missing_types: [], expiring_soon: []}`

### `salli advisor run [options] --json`
Run the Wealth Advisor and generate a fresh report.
  --trigger:  [default: manual]
Output: the advisor report (runs an LLM; slow).

## Other commands

### `salli accounts deactivate ACCOUNT_ID [options] --json`
Deactivate (soft-delete) an account.

### `salli accounts reactivate ACCOUNT_ID [options] --json`
Reactivate a previously deactivated account.

### `salli accounts show ACCOUNT_ID [options] --json`
Show an account's detail, current balance, and transaction history.
  --from: YYYY-MM-DD
  --to: YYYY-MM-DD

### `salli accounts update ACCOUNT_ID [options] --json`
Update an account's code, name, type, and currency.
  --code:  (required)
  --name:  (required)
  --type: asset|liability|equity|income|expense (required)
  --currency:  [default: LKR]

### `salli advisor apply REPORT_ID REC_ID [options] --json`
Apply a recommendation from an advisor report.

### `salli advisor briefing [options] --json`
Run the monthly financial-health briefing workflow (pauses for review before persisting).
  --thread-id: Resume an existing briefing thread

### `salli advisor daily-briefing [options] --json`
Show, or switch on/off, the scheduled daily advisor run.
  --on: Switch the daily run on or off

### `salli advisor dismiss REPORT_ID REC_ID [options] --json`
Dismiss a recommendation from an advisor report.

### `salli advisor reports [options] --json`
Advisor reports

### `salli advisor run-due [options] --json`
Run the advisor for every opted-in user due today. For a system cron job

### `salli agent audit-log [options] --json`
Show every agent-initiated write decision (approved or denied).
  --limit:  [default: 100]

### `salli agent chat [options] --json`
Start an interactive Tax Agent REPL (streamed responses).
  --thread-id: Continue a prior conversation

### `salli agent delete-session THREAD_ID [options] --json`
Delete a conversation.

### `salli agent history THREAD_ID [options] --json`
Print the full message history for a chat thread.

### `salli agent resume THREAD_ID [options] --json`
Resume an interactive chat REPL in an existing thread.

### `salli agent sessions [options] --json`
List past chat sessions.
  --limit:  [default: 50]

### `salli budget add [options] --json`
Create a budget for a period with per-category (expense account) limits.
  --period-start: YYYY-MM-DD (required)
  --period-end: YYYY-MM-DD (required)
  --line: ACCOUNT_ID:LIMIT_AMOUNT (repeat for multiple categories) (required) (repeatable)

### `salli budget delete BUDGET_ID [options] --json`
Delete a budget.

### `salli budget list [options] --json`
List budgets.

### `salli budget show BUDGET_ID [options] --json`
Show one budget.

### `salli budget update BUDGET_ID [options] --json`
Change a budget's period or replace its category limits.
  --period-start: YYYY-MM-DD
  --period-end: YYYY-MM-DD
  --line: ACCOUNT_ID:LIMIT_AMOUNT (repeat; replaces all lines) (repeatable)

### `salli db current [options] --json`
Show the revision each migration history is at.

### `salli db upgrade [options] --json`
Migrate the database: Salli's tables, then each enabled extension's.
  --revision: Target revision (Salli's history only) [default: head]

### `salli debt add NAME [options] --json`
Add a structured debt.
  --principal: Outstanding balance (required)
  --apr: Annual percentage rate, e.g. 0.18 for 18% (required)
  --minimum-payment:  (required)

### `salli debt delete DEBT_ID [options] --json`
Delete a debt.

### `salli debt list [options] --json`
List debts.
  --all: Include inactive debts

### `salli debt show DEBT_ID [options] --json`
Show one debt.

### `salli debt update DEBT_ID [options] --json`
Update fields on an existing debt.
  --name: 
  --principal: 
  --apr: 
  --minimum-payment: 
  --active: 

### `salli documents delete DOC_ID [options] --json`
Delete a document.

### `salli documents list [options] --json`
List uploaded documents.
  --namespace: 
  --search: 

### `salli documents show DOC_ID [options] --json`
Show a document's details.

### `salli documents upload FILE [options] --json`
Store a file, e.g. a receipt to attach to an entry (`entry add --receipt`).

### `salli entry list [options] --json`
List journal entries, with each posting and its tags.
  --from: YYYY-MM-DD
  --to: YYYY-MM-DD

### `salli entry parse TEXT [options] --json`
Draft an entry from free text (AI). Nothing is posted.

### `salli entry reverse ENTRY_ID [options] --json`
Post a reversing entry for a previously posted journal entry.

### `salli entry show ENTRY_ID [options] --json`
Show a journal entry's full detail and provenance (statement/receipt trace).

### `salli entry tag POSTING_ID [options] --json`
Replace a posting's tags. Never touches the posted amounts.
  --tag: Tag id (repeat; none clears the tags) (repeatable) [default: []]

### `salli fi goals [options] --json`
FI goals

### `salli fi history [options] --json`
Show FI score history.

### `salli fi projections [options] --json`
Show FI projection scenarios (conservative/base/growth).

### `salli fi score [options] --json`
Show the latest FI score, or recompute it.
  --recompute: Force a fresh computation

### `salli fi simulate-purchase AMOUNT [options] --json`
What a purchase costs you in months of freedom — cash vs. instalments.
  --term-months: Pay in instalments over N months
  --rate: Annual rate as a fraction, e.g. 0.18 for 18% [default: 0]

### `salli fi strategy [options] --json`
FIRE strategy

### `salli fi surplus [options] --json`
Show the monthly income/expense surplus breakdown.

### `salli insurance policy [options] --json`
Insurance policies

### `salli insurance target [options] --json`
Declared coverage targets

### `salli ledger income-statement [options] --json`
Print net income (income − expenses) for a date range.
  --from:  (required)
  --to:  (required)

### `salli ledger tags [options] --json`
List the tags you can put on postings.
  --kind: category | need

### `salli llm-keys delete PROVIDER [options] --json`
Remove your stored key for a provider.

### `salli llm-keys list [options] --json`
Which provider keys you have stored (never the keys themselves).

### `salli llm-keys set PROVIDER [options] --json`
Store your key for a provider (checked with the provider first).

### `salli mcp connections [options] --json`
AI clients currently connected.

### `salli mcp disable [options] --json`
Disconnect every AI client now and refuse new ones.

### `salli mcp enable [options] --json`
Allow AI clients to connect (each one still asks for your approval).

### `salli mcp revoke TOKEN_ID [options] --json`
Disconnect one AI client.

### `salli mcp status [options] --json`
Whether AI clients may connect to your Salli over MCP.

### `salli members add EMAIL [options] --json`
Let someone else (a partner, a household member) use this instance.

### `salli onboarding complete [options] --json`
Save your profile and create a starter chart of accounts. Safe to re-run.
  --name: Your name (required)
  --income: Comma-separated: employment,freelance,rental,interest,foreign,dividends
  --residency: resident | non_resident [default: resident]
  --primary-goal: financial_independence | retirement | home | emergency_fund | debt_free | wealth_growth
  --goal-amount: Target amount for that goal (LKR)
  --goal-year: Target year, YYYY

### `salli onboarding status [options] --json`
Whether first-run onboarding has been completed.

### `salli parse list [options] --json`
List uploaded statements, newest first.
  --limit: Maximum statements to show [default: 50]

### `salli parse pending [options] --json`
List transactions parsed but not yet posted.

### `salli parse post IDS [options] --json`
Post specific approved transactions to the ledger.

### `salli parse upload FILE [options] --json`
Parse a bank statement and queue transactions for review.
  --bank: Bank name hint (e.g. 'ComBank', 'HNB') [default: unknown]

### `salli portfolio add SYMBOL [options] --json`
Add an investment holding (manually declared, no live pricing).
  --name: Display name (required)
  --asset-class: e.g. equity, bond, cash, crypto (required)
  --cost-basis: Total amount invested (required)
  --current-value: Total current worth (required)

### `salli portfolio delete HOLDING_ID [options] --json`
Delete a holding.

### `salli portfolio list [options] --json`
List investment holdings.
  --all: Include inactive holdings

### `salli portfolio show HOLDING_ID [options] --json`
Show one holding.

### `salli portfolio update HOLDING_ID [options] --json`
Update fields on an existing holding.
  --symbol: 
  --name: 
  --asset-class: 
  --cost-basis: 
  --current-value: 
  --active: 

### `salli profile balance-sheet [options] --json`
Declare opening balances — posts real journal entries (asset|liability).
  --balance: CODE:NAME:TYPE:AMOUNT (repeat) (required) (repeatable)

### `salli profile delete-account [options] --json`
Permanently delete every row belonging to your account. Irreversible.
  --confirm: Skip the interactive confirmation prompt

### `salli profile export [options] --json`
Export everything Salli has stored about you as one JSON document.
  --output: Output JSON file path (required)

### `salli profile income [options] --json`
Declare income sources — posts one representative monthly entry each.
  --income: CODE:NAME:AMOUNT (repeat) (required) (repeatable)
  --deposit-account-code:  [default: 1200]
  --deposit-account-name:  [default: Bank Account]

### `salli profile risk-questionnaire [options] --json`
Submit the risk-tolerance questionnaire and persist the scored result.
  --time-horizon-years:  (required)
  --drawdown-reaction: sell_all|sell_some|hold|buy_more (required)
  --income-stability: unstable|moderate|stable (required)
  --investment-experience: none|some|experienced (required)
  --dependents-count: 

### `salli profile update [options] --json`
Update identity fields on the fact-find profile.
  --display-name: 
  --date-of-birth: YYYY-MM-DD
  --dependents-count: 
  --employment-status: employed|self_employed|unemployed|student|retired
  --employment-type: permanent|contract|self_employed|other
  --residency-status: resident|non_resident
  --employer: 
  --ird-number: 

### `salli reminders delete REMINDER_ID [options] --json`
Delete a reminder.

### `salli reminders done REMINDER_ID [options] --json`
Mark a reminder as done.

### `salli reminders list [options] --json`
List reminders.
  --status: Filter by status, e.g. 'pending'/'done'
  --alerts-only: Show only system-detected alerts, not user-created reminders

### `salli reminders seed [options] --json`
Seed the standard filing calendar for a year of assessment.
  --year: Year of assessment [default: 2025/26]

### `salli reminders sync-alerts [options] --json`
Detect current Budget/Subscription/Insurance alert conditions and

### `salli reports balance-sheet [options] --json`
Show the balance sheet: assets, liabilities, equity, and net worth.

### `salli reports export REPORT_TYPE [options] --json`
Export a report as CSV.
  --output: Output CSV file path (required)

### `salli reports goal-progress [options] --json`
Show progress toward all active FI goals.

### `salli reports net-worth [options] --json`
Show current net worth and its historical trend.

### `salli serve [options] --json`
Run the HTTP API and the MCP server.
  --host: Interface to bind [default: 127.0.0.1]
  --port: Port [default: 8000]
  --reload: Reload on code changes (development)

### `salli setup [options] --json`
Set up this instance: config, database, and your owner account.
  --email: The owner's email (prompted if omitted)
  --name: The owner's name (defaults to the email's name part)
  --income: Comma-separated income sources for the starter accounts: employment,freelance,rental,interest,foreign,dividends
  --skip-llm-key: Do not ask for an Anthropic API key

### `salli skills install [options] --json`
Copy the skills where Claude Code finds them.
  --project: Install into ./.claude/skills instead of ~/.claude/skills
  --force: Overwrite skills that are already installed

### `salli skills list [options] --json`
List the bundled skills.

### `salli subscription add NAME [options] --json`
Add a recurring subscription.
  --amount: Expected charge amount (required)
  --frequency: weekly|monthly|quarterly|yearly (required)
  --next-due-date: YYYY-MM-DD (required)
  --account-id: Restrict matching to this expense account
  --grace-days:  [default: 5]
  --tolerance:  [default: 0.05]

### `salli subscription delete SUBSCRIPTION_ID [options] --json`
Delete a subscription.

### `salli subscription list [options] --json`
List recurring subscriptions.
  --all: Include inactive subscriptions

### `salli subscription show SUBSCRIPTION_ID [options] --json`
Show one subscription.

### `salli subscription update SUBSCRIPTION_ID [options] --json`
Update fields on an existing subscription.
  --name: 
  --amount: 
  --frequency: 
  --next-due-date: 
  --account-id: 
  --grace-days: 
  --tolerance: 
  --active: 

### `salli tax explain [options] --json`
Launch the Tax Agent REPL to explain your tax situation.
  --year:  [default: 2025/26]

### `salli tax latest [options] --json`
Show the most recently stored tax computation for a year.
  --year: Year of assessment [default: 2025/26]

### `salli tax prepare-return [options] --json`
Run the return preparation workflow (pauses for review before finalizing).
  --year:  [default: 2025/26]
  --thread-id: Resume an existing return thread

### `salli tax recompute-stored [options] --json`
Re-run every stored tax computation against the current engine.
  --apply: Actually write the corrected results. Without this, only reports what would change.

### `salli whoami [options] --json`
The user this CLI acts as.
