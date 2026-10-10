"""Interface-description size for Salli's MCP server and CLI help (Section 4.2).

Must run inside Salli's environment at the paper's snapshot (84a7d1e), with
tiktoken available; reproduce.sh exports that snapshot and runs:
  uv run --project <export> --with tiktoken python measure_interface_tokens.py
Lists the MCP tools exactly as a client receives them (services are mocked; no
database is touched) and runs `salli <group> --help` for every group. Token
counts use tiktoken's o200k_base as a proxy; providers' tokenizers differ.
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import subprocess
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-dummy")

import tiktoken  # noqa: E402

from salli.interfaces.api.mcp_server import build_mcp_server  # noqa: E402

enc = tiktoken.get_encoding("o200k_base")
GROUPS = ["accounts", "entry", "ledger", "tax", "agent", "parse", "reminders", "fi", "advisor",
          "documents", "billing", "profile", "budget", "debt", "portfolio", "subscription",
          "insurance", "reports", "bug-reports"]


def help_tokens(args: list[str]) -> int:
    env = {**os.environ, "NO_COLOR": "1", "TERM": "dumb", "COLUMNS": "100"}
    out = subprocess.run([shutil.which("salli") or "salli", *args, "--help"],
                         capture_output=True, text=True, env=env).stdout
    return len(enc.encode(out))


def main() -> None:
    mcp = build_mcp_server(services=MagicMock(), issuer_url="https://example.com")
    tools = asyncio.run(mcp.list_tools())
    defs = json.dumps([t.model_dump(exclude_none=True, mode="json") for t in tools])
    groups = {g: help_tokens([g]) for g in GROUPS}
    print(json.dumps({
        "mcp_tools": len(tools),
        "mcp_definition_chars": len(defs),
        "mcp_definition_tokens_o200k": len(enc.encode(defs)),
        "cli_top_help_tokens": help_tokens([]),
        "cli_group_help_tokens": groups,
        "cli_group_help_min": min(groups.values()),
        "cli_group_help_max": max(groups.values()),
    }, indent=2))


if __name__ == "__main__":
    main()
