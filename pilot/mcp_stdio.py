"""salli-core's own MCP server over stdio, acting as SALLI_USER_ID.

The hosted server authenticates every request with OAuth and reads the user
from the access token. For the pilot the agent and the server run on one
machine, so the token lookup is replaced by the user id from the
environment. The 24 tools, their schemas and their implementations are
salli-core's unchanged.
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
server.run(transport="stdio")
