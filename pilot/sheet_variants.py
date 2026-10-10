"""Command-sheet ablation (agenda S3): which part of the sheet matters?

Derives four variants from the sheet the paper used (cli_reference.md), so
each one differs from it in a single element and keeps the same header:

  noout   usage, description and options; the JSON output shapes removed
  noopts  usage, description and output shapes; the options removed
  names   usage line and one-line description only (scope alone)
  wide    the full sheet, plus usage and options for every other CLI command
          (no output shapes), to test a larger scope

  $SALLI/.venv/bin/python pilot/sheet_variants.py
writes pilot/cli_reference_<variant>.md and prints each one's size in tokens.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
BASE = (HERE / "cli_reference.md").read_text()


def blocks(text: str) -> tuple[str, list[list[str]]]:
    head, *rest = re.split(r"\n(?=### )", text.strip())
    return head, [b.splitlines() for b in rest]


def build(keep_opts: bool, keep_out: bool, keep_doc: bool = True) -> str:
    head, bs = blocks(BASE)
    out = []
    for b in bs:
        lines = [b[0]]
        for ln in b[1:]:
            if ln.startswith("  --"):
                if keep_opts:
                    lines.append(ln)
            elif ln.startswith("Output:"):
                if keep_out:
                    lines.append(ln)
            elif keep_doc:
                lines.append(ln)
        out.append("\n".join(lines))
    return head + "\n\n" + "\n\n".join(out) + "\n"


def wide() -> str:
    sys.path.insert(0, str(HERE))
    from cli_reference import EQUIVALENTS, describe  # noqa: E402  (loads salli's env)
    from salli.interfaces.cli.main import cli

    covered = {p for _, p in EQUIVALENTS}
    root = cli()
    extra = []
    for gname, group in sorted(root.commands.items()):
        subs = getattr(group, "commands", None)
        if not subs:
            path = gname
            if path not in covered:
                extra.append(describe(path, group))
            continue
        for cname, cmd in sorted(subs.items()):
            path = f"{gname} {cname}"
            if path not in covered:
                extra.append(describe(path, cmd))
    return BASE.rstrip() + "\n\n## Other commands\n\n" + "\n\n".join(extra) + "\n"


def tokens(text: str) -> int | None:
    try:
        import tiktoken
        return len(tiktoken.get_encoding("o200k_base").encode(text))
    except ImportError:
        return None


def main() -> None:
    variants = {
        "noout": build(keep_opts=True, keep_out=False),
        "noopts": build(keep_opts=False, keep_out=True),
        "names": build(keep_opts=False, keep_out=False),
        "wide": wide(),
    }
    rows = [("full", tokens(BASE), BASE.count("### "))]
    for name, text in variants.items():
        (HERE / f"cli_reference_{name}.md").write_text(text)
        rows.append((name, tokens(text), text.count("### ")))
    out = HERE.parent / "data" / "pilot-ablation" / "sheet_tokens.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("variant,tokens,commands\n" + "".join(f"{v},{t},{c}\n" for v, t, c in rows))
    for v, t, c in rows:
        print(f"{v}: {t} tokens, {c} commands")


if __name__ == "__main__":
    main()
