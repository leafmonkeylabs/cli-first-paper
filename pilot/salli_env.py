"""Load a salli-core checkout's .env and build its services.

Run every pilot script with that checkout's interpreter, e.g.
  $SALLI/.venv/bin/python pilot/run.py ...
so that `import salli` resolves to the pinned checkout.
"""

from __future__ import annotations

import os
from functools import cache
from pathlib import Path

SALLI = Path(os.environ.get("SALLI", Path(__file__).parent / "work" / "salli-core")).resolve()


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
