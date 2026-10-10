"""Load the v2 salli-core checkout's .env and build its services.

As pilot/salli_env.py, for the rewritten core (salli-core 1322f84). Run every
v2 script with that checkout's interpreter, e.g.
  $SALLI/.venv/bin/python pilot/v2/run.py ...
so that `import salli` resolves to the pinned checkout.

New for v2: the CLI is a client of the API server, so the harness also needs
the server's URL (SALLI_SERVER) and the CLI's entry point (salli.js).
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

HERE = Path(__file__).parent
SALLI = Path(os.environ.get("SALLI", HERE.parent / "work" / "salli-core-v2")).resolve()
# The API server the CLI arms talk to (pilot/v2/README.md says how to start it).
SERVER = os.environ.get("SALLI_SERVER", "http://127.0.0.1:55680")
CLI_JS = SALLI / "packages" / "cli" / "dist" / "salli.js"
NODE = os.environ.get("NODE_BIN", "/opt/homebrew/bin/node")


def salli_env() -> dict[str, str]:
    """The checkout's .env as a dict (values unquoted)."""
    env: dict[str, str] = {}
    for line in (SALLI / ".env").read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def load() -> None:
    for k, v in salli_env().items():
        os.environ.setdefault(k, v)


@cache
def services():
    load()
    from salli.composition import build_services
    from salli.config import get_settings

    return build_services(get_settings())
