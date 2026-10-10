"""The 24 MCP tools that made up the paper's MCP-24 at 0277747.

All 24 exist under the same names at 1322f84. The isolation wave's mcp-24
configuration serves only these tools, using 1322f84's schemas.
"""
MCP24_TOOLS = (
    "create_account", "create_reminder", "delete_document", "explain_tax_band", "get_accounts",
    "get_budget_summary", "get_coverage_report", "get_financial_profile", "get_latest_advisor_report",
    "get_memory", "get_payoff_plan", "get_portfolio_summary", "get_subscription_report",
    "get_tax_computation", "get_trial_balance", "list_documents", "list_memories", "list_tax_packs",
    "post_journal_entry", "read_document", "run_wealth_advisor", "save_document", "save_memory",
    "update_document",
)
assert len(MCP24_TOOLS) == 24
