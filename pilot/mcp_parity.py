"""An MCP server at full parity with the salli CLI, over stdio.

One tool per CLI command that supports --json (administrative groups
excluded). Each tool's parameters are the command's arguments and options, its
description is the command's help, and calling it runs `salli <command> ...
--json`, returning exactly what the CLI prints. The two surfaces then differ
only in protocol: tool schemas in every request versus a shell.

This is the shape of an MCP server generated from an existing interface, the
case the "MCP costs context" argument has in mind; salli-core's own server is
a curated 24-tool subset.
"""

from __future__ import annotations

import inspect
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from salli_env import SALLI, load  # noqa: E402

load()

from mcp.server.fastmcp import FastMCP  # noqa: E402

from salli.interfaces.cli.main import cli  # noqa: E402

EXCLUDED_GROUPS = {"db", "mcp", "members", "skills", "llm-keys", "setup", "serve", "whoami", "onboarding"}
SALLI_BIN = str(SALLI / ".venv" / "bin" / "salli")


def leaf_commands(group, path=()):
    for name, c in group.commands.items():
        if hasattr(c, "commands"):
            yield from leaf_commands(c, path + (name,))
        else:
            yield path + (name,), c


def make_tool(path: tuple[str, ...], cmd):
    params = [p for p in cmd.params if p.name not in ("json", "help")]
    sig_params, specs = [], []
    for p in params:
        pname = p.name
        if p.param_type_name == "argument":
            ann, default = str, inspect.Parameter.empty
            specs.append(("arg", pname, None))
        elif getattr(p, "is_flag", False):
            ann, default = bool, bool(p.default)
            on = next((o for o in p.opts if o.startswith("--")), p.opts[0])
            off = next((o for o in getattr(p, "secondary_opts", []) if o.startswith("--")), None)
            specs.append(("flag", pname, (on, off)))
        elif getattr(p, "multiple", False):
            ann, default = list[str] | None, None
            specs.append(("multi", pname, max(p.opts, key=len)))
        else:
            ann = str if p.required else str | None
            default = inspect.Parameter.empty if p.required else (None if p.default in (None, "", ()) else str(p.default))
            specs.append(("opt", pname, max(p.opts, key=len)))
        sig_params.append(inspect.Parameter(pname, inspect.Parameter.KEYWORD_ONLY, annotation=ann, default=default))
    # Required keyword-only parameters may follow optional ones, so no reordering is needed.

    def run(**kwargs: Any) -> Any:
        argv = [SALLI_BIN, *path]
        for kind, pname, extra in specs:
            v = kwargs.get(pname)
            if kind == "arg":
                argv.append(str(v))
            elif kind == "flag":
                on, off = extra
                if v:
                    argv.append(on)
                elif off:
                    argv.append(off)
            elif kind == "multi":
                for item in v or []:
                    argv += [extra, str(item)]
            elif v is not None:
                argv += [extra, str(v)]
        argv.append("--json")
        out = subprocess.run(argv, capture_output=True, text=True, env=os.environ, timeout=300)
        if out.returncode != 0:
            return {"error": out.stderr.strip()[-2000:], "exit_code": out.returncode}
        try:
            return json.loads(out.stdout)
        except json.JSONDecodeError:
            return {"output": out.stdout.strip()}

    run.__signature__ = inspect.Signature(sig_params, return_annotation=Any)
    run.__annotations__ = {p.name: p.annotation for p in sig_params} | {"return": Any}
    run.__name__ = "_".join(path).replace("-", "_")
    run.__doc__ = (cmd.help or "").strip()
    return run


def build() -> FastMCP:
    server = FastMCP(name="Salli", instructions=(
        "Access to one user's Salli financial data: the ledger, tax, budgets, debts, "
        "portfolio, subscriptions, insurance, financial independence, reports and the "
        "advisor. Every tool corresponds to a `salli` CLI command and returns its JSON output."
    ))
    for path, cmd in leaf_commands(cli()):
        if path[0] in EXCLUDED_GROUPS or not any(p.name == "json" for p in cmd.params):
            continue
        fn = make_tool(path, cmd)
        server.add_tool(fn, name=fn.__name__, description=fn.__doc__)
    return server


if __name__ == "__main__":
    srv = build()
    if "--list" in sys.argv:
        import asyncio
        tools = asyncio.run(srv.list_tools())
        print(len(tools), "tools,", sum(len(json.dumps(t.model_dump(exclude_none=True))) for t in tools), "chars")
    else:
        srv.run(transport="stdio")
