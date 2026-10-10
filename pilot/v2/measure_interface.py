"""Interface-description sizes for the rewritten core (follow-up, Section 7.2).

Same method as scripts/measure_interface_tokens.py:
- MCP tools are listed exactly as a client receives them, with services mocked
  and no database touched;
- the command sheets are counted as given to the agents;
- tiktoken o200k_base is the proxy tokenizer.

Run inside the v2 checkout's environment:
  uv run --project pilot/work/salli-core-v2 --with tiktoken python pilot/v2/measure_interface.py
Writes data/pilot-v2/interface_tokens.json.
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://x:y@localhost/z")
os.environ.setdefault("ANTHROPIC_API_KEY", "sk-dummy")

import tiktoken  # noqa: E402

from salli.interfaces.api.mcp_server import build_mcp_server  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
enc = tiktoken.get_encoding("o200k_base")


def main() -> None:
    mcp = build_mcp_server(services=MagicMock(), issuer_url="https://example.com")
    tools = asyncio.run(mcp.list_tools())
    defs = json.dumps([t.model_dump(exclude_none=True, mode="json") for t in tools])
    sheet = (HERE / "cli_reference.md").read_text()
    old_sheet = (ROOT / "pilot" / "cli_reference.md").read_text()
    out = {
        "mcp_tools": len(tools),
        "mcp_definition_tokens_o200k": len(enc.encode(defs)),
        "sheet_commands": sheet.count("### "),
        "sheet_tokens_o200k": len(enc.encode(sheet)),
        "paper_sheet_commands": old_sheet.count("### "),
        "paper_sheet_tokens_o200k": len(enc.encode(old_sheet)),
    }
    (ROOT / "data" / "pilot-v2" / "interface_tokens.json").write_text(json.dumps(out, indent=2) + "\n")
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
