"""salli-core's own MCP server over stdio, acting as SALLI_USER_ID (v2: 1322f84).

As pilot/mcp_stdio.py. The hosted server authenticates every request with
OAuth and reads the user from the access token. For the pilot the agent and
the server run on one machine, so the token lookup is replaced by the user id
from the environment. The tools, their schemas and their implementations are
salli-core's unchanged (src/salli/interfaces/api/mcp_server.py).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from salli_env import services  # noqa: E402

svc = services()

import salli.interfaces.api.mcp_server as mcp_server  # noqa: E402

USER = os.environ["SALLI_USER_ID"]
mcp_server._current_user_id = lambda: USER

server = mcp_server.build_mcp_server(svc, issuer_url="http://localhost:8000")
# Follow-up isolation wave: SALLI_MCP_TOOLS (comma-separated) keeps only those
# tools, e.g. the 24 that made up the paper's MCP-24 at 0277747. The kept tools'
# schemas and implementations are 1322f84's, unchanged.
keep = [t for t in os.environ.get("SALLI_MCP_TOOLS", "").split(",") if t]
if keep:
    for name in [t.name for t in server._tool_manager.list_tools()]:
        if name not in keep:
            server.remove_tool(name)
server.run(transport="stdio")
