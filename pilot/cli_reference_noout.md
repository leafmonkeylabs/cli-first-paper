# salli CLI reference

Every command prints one JSON document on stdout with --json; messages go to stderr; a non-zero exit code means it failed. Money is a decimal string. Ids can be shortened to a unique prefix. `jq` is available.


### `salli accounts list [options] --json`
List all accounts in the chart of accounts.

### `salli accounts add CODE NAME TYPE [options] --json`
Add an account to the chart of accounts.
  --currency: ISO currency code [default: LKR]

### `salli entry add [options] --json`
Add a balanced journal entry (ACCOUNT_ID:AMOUNT pairs).
  --date: YYYY-MM-DD (required)
  --desc: Description (required)
  --debit: ACCOUNT_ID:AMOUNT (repeat for splits) (required) (repeatable)
  --credit: ACCOUNT_ID:AMOUNT (repeat for splits) (required) (repeatable)
  --receipt: Document ID of an attached receipt/file (source stays 'manual')

### `salli ledger trial-balance [options] --json`
Print the trial balance (must net to zero).
  --from: YYYY-MM-DD
  --to: YYYY-MM-DD

### `salli tax compute [options] --json`
Compute income tax using the versioned rules engine.
  --year: Year of assessment [default: 2025/26]

### `salli tax packs [options] --json`
List available tax packs.

### `salli reminders add KIND [options] --json`
Create a reminder.
  --due-date: YYYY-MM-DD (required)

### `salli profile show [options] --json`
Show the fact-find profile: identity, risk profile, life stage.

### `salli budget summary BUDGET_ID [options] --json`
Show category limits vs. actual ledger spend for a budget's period.

### `salli debt payoff-plan [options] --json`
Show the avalanche/snowball payoff plan for all active debts.
  --extra: Extra monthly payment [default: 0]
  --strategy: avalanche (highest APR first) or snowball (smallest balance first) [default: avalanche]

### `salli portfolio summary [options] --json`
Show allocation by asset class, total gain/ROI, and rebalancing alerts.
  --target: ASSET_CLASS:FRACTION, e.g. equity:0.7 (repeat); omit to skip rebalancing alerts (repeatable) [default: []]

### `salli subscription report SUBSCRIPTION_ID [options] --json`
Show missed-charge/price-change report(s).

### `salli insurance report [options] --json`
Show the coverage-gap report: target vs. actual coverage, missing types,

### `salli advisor run [options] --json`
Run the Wealth Advisor and generate a fresh report.
  --trigger:  [default: manual]
