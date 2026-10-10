# salli CLI reference

Every command prints one JSON document on stdout with --json; messages go to stderr; a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened to a unique prefix. `jq` is available.

### `salli accounts list [options] --json`
List accounts
  --type <type>: Only this type (choices: "asset", "liability", "equity", "income", "expense")
  --active: Only active accounts
  --balances: Add each account’s balance (in your base currency)
Output: `[{id: str, code: str, name: str, type: str, currency: str, parent_id: null, is_active: bool, tax_role: null}, ...]`

### `salli accounts add [CODE] [NAME] [TYPE] [options] --json`
Add an account
  CODE: Account code, e.g. 1300
  NAME: Account name, e.g. Brokerage
  TYPE: One of: asset, liability, equity, income, expense
  --currency <code>: Currency it is held in (default: your base currency)
  --parent <account>: Parent account (code, name or id)
  --tax-role <role>: How the tax engine treats it (choices: "apit_credit", "ait_credit", "foreign_tax_credit", "qualifying_payment", "fsi_income")
Output: `{id: str}`

### `salli entries add [options] --json`
Post a balanced entry from ACCOUNT:AMOUNT pairs
  --desc <text>: What it was
  --date <date>: When (YYYY-MM-DD, today, yesterday) (default: "today")
  --debit <account:amount>: The receiving side (repeat to split)
  --credit <account:amount>: The giving side (repeat to split)
  --currency <code>: Currency of the amounts (default: your base currency)
  --fx-rate <rate>: Units of your base currency per unit of --currency (default: the published rate)
  --tag <axis=slug>: Tag the debit side, e.g. category=groceries (repeatable)
  --receipt <document-id>: Attach a stored document (see `salli documents`)
Output: `{id: str}`

### `salli ledger trial-balance [options] --json`
Every account’s balance; debits and credits net to zero
  --from <date>: From this date (YYYY-MM-DD)
  --to <date>: Up to this date
Output: `{currency: str, balances: {<account_id>: "<decimal>"}, net: "<decimal>"}`

### `salli tax compute [options] --json`
Compute your income tax from the ledger (and store the result)
  --year <year>: Year of assessment, e.g. 2025/26 (default: the server’s)
Output: `{pack_country: str, pack_year: str, pack_version: str, currency: str, gross_income: "<decimal>", foreign_service_income: "<decimal>", regular_income: "<decimal>", personal_relief_applied: "<decimal>", qp_deduction: "<decimal>", taxable_income: "<decimal>", fsi_tax: "<decimal>", tax_before_credits: "<decimal>", apit_credit: "<decimal>", ait_credit: "<decimal>", foreign_tax_credit: "<decimal>", total_credits: "<decimal>", tax_payable: "<decimal>", refund_due: "<decimal>", rounding: str, band_workings: [{...}, ...]}`

### `salli tax packs [options] --json`
The tax packs this server has
Output: `[{country: str, year: str, version: str, currency: str, period_start: str, period_end: str, personal_relief: "<decimal>", return_due: str, set_due: str, installments: [str, ...], final_installment_due: str, withholding_kinds: [{...}, ...], tax_roles: [str, ...]}, ...]`

### `salli reminders add WHAT [options] --json`
Add a reminder
  WHAT: What to remember, e.g. quarterly_installment
  --due <date>: When (YYYY-MM-DD)
Output: `{id: str}`

### `salli profile get [options] --json`
Show your profile
Output: `{id: str, email: str, display_name: str, base_currency: str, date_of_birth: null, dependents_count: null, employment_status: null, residency_status: str, employer: null, employment_type: null, ird_number: null, risk_score: null, risk_category: null, life_stage: str, mcp_enabled: bool, daily_briefing_enabled: bool, preferred_model: null, tax_residency: str, tax_ids: [], nic: null, fi_assumptions: {inflation: null, real_return: null, safe_withdrawal_rate: null}}`

### `salli budgets summary BUDGET [options] --json`
Limits against actual spending for the budget’s period
  BUDGET: Budget id (or its start)
Output: JSON (no sample data in the seeded ledger).

### `salli debts payoff-plan [options] --json`
How long paying off your debts takes, and what it costs
  --strategy <strategy>: avalanche: highest rate first; snowball: smallest balance first (choices: "avalanche", "snowball", default: "avalanche")
  --extra <amount>: Paid on top of the minimums each month (default: "0")
  --months <n>: Months of the schedule to show (default: 12)
Output: `{strategy: str, currency: str, months_to_payoff: number, total_interest_paid: "<decimal>", schedule: [{...}, ...]}`

### `salli portfolio summary [options] --json`
Value, gain, allocation and rebalancing
  --target <class:fraction>: A target allocation, e.g. equity:0.6 (repeatable) for rebalancing alerts
Output: `{currency: str, total_value: "<decimal>", total_cost_basis: "<decimal>", total_gain: "<decimal>", total_gain_pct: "<decimal>", allocation: [], alerts: [], notes: []}`

### `salli subscriptions report [SUBSCRIPTION] [options] --json`
Missed charges and price changes
  SUBSCRIPTION: One subscription (default: all)
Output: `{reports: []}`

### `salli insurance report [options] --json`
Cover against your targets, missing types, and policies expiring soon
Output: `{currency: str, lines: [], missing_types: [], expiring_soon: []}`

### `salli advisor run [options] --json`
Run the advisor now (an AI call)
Output: the advisor report (runs an LLM; slow).

### `salli advisor latest [options] --json`
Show the most recent report
Output: JSON (no sample data in the seeded ledger).

### `salli documents list [options] --json`
List documents
  --search <text>: Search titles and contents
  --namespace <ns>: documents or memories (choices: "documents", "memories")
Output: `{documents: [{...}, ...], count: number}`

### `salli documents upload FILE [options] --json`
Store a file (e.g. a receipt to attach: salli entries add --receipt <id>)
  FILE: A file: PDF, image, CSV, text, Excel
Output: `{file_ref: str, name: str, size: number, mime_type: str}`

### `salli documents show DOCUMENT [options] --json`
Show a document
  DOCUMENT: Document id (or its start)
Output: `{id: str, user_id: str, title: str, content: null, storage_key: str, mime_type: str, tags: [str, ...], source: str, namespace: str, slug: null, description: null, created_at: str, updated_at: str}`

### `salli documents delete DOCUMENT [options] --json`
Delete a document
  DOCUMENT: Document id (or its start)
  --yes: Do not ask for confirmation
Output: `{id: str, deleted: bool}`

### `salli insights cash-flow [options] --json`
Income, spending, what was left and the savings rate, month by month
  --months <n>: Months, ending this one (default 12)
Output: `{currency: str, months: [{...}, ...]}`

### `salli insights spending [options] --json`
Where the money went, largest first
  --months <n>: Months, ending this one (default 3)
  --by <axis>: Group by (choices: "category", "account", "need", default: "category")
Output: `{currency: str, by: str, months: [str, ...], lines: []}`

### `salli insights net-worth [options] --json`
What you own less what you owe, at the end of each month
  --months <n>: Month ends to show (default 24)
Output: `{currency: str, points: [{...}, ...]}`

### `salli insights recurring [options] --json`
Payments that keep coming back, and whether you track them as subscriptions
Output: `{items: []}`

### `salli insights forecast [options] --json`
Where your cash is heading: the lowest point, and what moves it
  --days <n>: How many days ahead (default 60)
  --flows <n>: How many upcoming flows to list (default: 10)
Output: `{currency: str, start: str, end: str, today: "<decimal>", end_balance: "<decimal>", lowest: "<decimal>", lowest_date: str, daily: [{...}, ...], accounts: [], flows: [], notes: []}`

### `salli insights safe-to-spend [options] --json`
What could go out today without your cash running out before payday
Output: `{currency: str, amount: "<decimal>", cash_today: "<decimal>", until: str, next_income: null, committed: [], notes: []}`

### `salli insights signals [options] --json`
What in your finances needs your attention now
Output: `{signals: []}`

### `salli fi simulate-purchase AMOUNT [options] --json`
What a purchase costs you in months of freedom: cash against instalments
  AMOUNT: The price
  --months <n>: Pay in instalments over this many months
  --rate <rate>: The instalments’ annual interest: 0.18 or 18% (default: "0")
Output: `{amount: "<decimal>", currency: str, fi_number: "<decimal>", fi_asset_base_before: "<decimal>", monthly_surplus: "<decimal>", baseline_months_to_fi: number, payable_from_liquid: bool, emergency_months_before: "<decimal>", emergency_months_after_cash: "<decimal>", emergency_fund_target_months: number, options: [{...}, ...], cheapest_option_key: str, data_as_of: str, is_stale: bool, stale_after_days: number, real_return_used: "<decimal>", swr: "<decimal>", assumptions: {region: str, inflation: {...}, real_return: {...}, safe_withdrawal_rate: {...}}}`

### `salli statements pending [STATEMENT] [options] --json`
Transactions read from statements but not posted or discarded yet
  STATEMENT: A statement id (or its start); default: every statement
Output: `{transactions: []}`

### `salli statements categorize TRANSACTION ACCOUNT [options] --json`
Choose where a pending transaction goes before posting it
  TRANSACTION: A pending transaction id (or its start)
  ACCOUNT: Where the money came from or went (code, name or id)
  --category <slug>: Tag it with this category
  --need <need>: Tag it with this need (choices: "essential", "discretionary", "savings")
Output: JSON (no sample data in the seeded ledger).

### `salli statements post STATEMENT [TRANSACTIONS...] [options] --json`
Post pending transactions to the ledger
  STATEMENT: Statement id (or its start)
  TRANSACTIONS: Transaction ids (or their starts) to post
  --all: Every pending transaction that is complete and not a possible duplicate
  --yes: Do not ask for confirmation
Output: JSON (no sample data in the seeded ledger).

### `salli statements discard STATEMENT [TRANSACTIONS...] [options] --json`
Discard pending transactions: they are never posted and leave review
  STATEMENT: Statement id (or its start)
  TRANSACTIONS: Transaction ids (or their starts); default: every pending one
  --yes: Do not ask for confirmation
Output: JSON (no sample data in the seeded ledger).

### `salli rules suggest [options] --json`
Rules your own bookkeeping implies (nothing is added until you add it)
Output: `[{name: str, conditions: [{...}, ...], actions: {...}, priority: number, match_all: bool, enabled: bool, support: number, agreement: number, examples: [str, ...]}, ...]`

### `salli rules add NAME [options] --json`
Add a rule (see what it would do first with `salli rules test`)
  NAME: What the rule is, e.g. "Uber rides"
  --if <condition>: A condition: FIELD OPERATOR VALUE, e.g. "description contains uber" (repeatable)
  --account <account>: Book the other side to this account (code, name or id)
  --category <slug>: Tag it with this category
  --need <need>: Tag it with this need (choices: "essential", "discretionary", "savings")
  --rename <description>: Replace the bank’s description with this
  --priority <n>: Lower runs first (default 100)
  --any: Match when any condition holds (default: all of them)
Output: `{id: str}`

