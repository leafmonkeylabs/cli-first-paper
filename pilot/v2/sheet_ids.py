"""The isolation wave's IDs-only command sheet (paper Section 7.3).

cli_reference.md with account arguments documented as ids: "(code, name or id)"
becomes "(id)" and entries add's "<account:amount>" becomes "<account-id:amount>".
Nothing else changes. The run harness also makes the salli wrapper refuse
account codes and names for this configuration, so both protocols address
accounts the same way.

  python3 pilot/v2/sheet_ids.py   -> pilot/v2/cli_reference_ids.md
"""
from pathlib import Path

HERE = Path(__file__).resolve().parent
src = (HERE / "cli_reference.md").read_text()
out = src.replace("(code, name or id)", "(id)").replace("<account:amount>", "<account-id:amount>")
(HERE / "cli_reference_ids.md").write_text(out)
changed = sum(a != b for a, b in zip(src.splitlines(), out.splitlines()))
print(f"cli_reference_ids.md: {changed} lines changed")
