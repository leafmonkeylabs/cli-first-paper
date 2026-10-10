"""RQ1 pilot: the same tasks on the same product, through MCP or the CLI.

Arms
  mcp               salli-core's MCP server (24 tools); no shell.
  cli-step          the salli CLI through Bash, one salli command per call (only
                    `salli` is permitted, so pipes and other programs are
                    refused), with salli-core's CLI skill in the system prompt.
  cli-pipe          the salli CLI through Bash with jq and shell composition
                    allowed, an instruction to compose dependent steps, and the
                    skill.
  cli-pipe-noskill  as cli-pipe without the skill: commands are found through
                    --help alone.
  mcp-parity        an MCP server generated from the CLI (mcp_parity.py): one
                    tool per command with --json, 102 tools, each returning
                    exactly the CLI's output; the surfaces differ only in protocol.
  cli-pipe-skills   as cli-pipe-noskill, plus salli-core's five skills installed
                    with `salli skills install --project` and the Skill tool on:
                    the agent sees each skill's description and loads it if it
                    chooses, as in a real self-hosted setup.
  cli-step-ref      as cli-step, but with a generated reference of the commands
  cli-pipe-ref      and cli-pipe, equivalent to the MCP tools and their JSON
                    output shapes (pilot/cli_reference.md) in place of the skill:
                    the agent knows the commands before it starts.

Every run gets a freshly seeded user, so runs are independent and verified
against database state. The agent is Claude Code in headless mode with its
default system prompt replaced, user settings and CLAUDE.md excluded, and only
the arm's tools available.

Usage (with the salli-core checkout's interpreter):
  $SALLI/.venv/bin/python pilot/run.py --models haiku sonnet --reps 3 --jobs 4
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import gzip
import json
import os
import shutil
import sys
import time
import uuid
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from salli_env import SALLI, salli_env  # noqa: E402
from seed import make_user  # noqa: E402
from tasks import TASKS  # noqa: E402

ROOT = HERE.parent
OUT = Path(os.environ.get("PILOT_OUT", ROOT / "data" / "pilot"))
RUNS_CSV = OUT / "runs.csv"
WORK = HERE / "work" / "runs"
SIZE_SEED = {"small": 1, "large": 2}

CLAUDE = os.environ.get("CLAUDE_BIN") or shutil.which("claude") or "claude"

SYSTEM = (
    "You are an assistant operating the user's personal finance app, Salli, on their "
    "behalf. Complete the user's request with the tools available. Do not ask the user "
    "questions; make reasonable choices. Money figures must come from Salli, not from "
    "your own arithmetic. The request itself is the user's confirmation for any change it "
    "asks for. Today is 2026-04-01. When you have finished, end your reply "
    "with a line 'FINAL: <short answer or summary>'.\n\n"
)
SKILL = (SALLI / "src" / "salli" / "skills" / "salli-cli" / "SKILL.md").read_text().split("---", 2)[-1].strip()
CLI_STEP = (
    "Use the `salli` command-line tool through the Bash tool. Run exactly one salli "
    "command per Bash call, without pipes, command substitution, loops or other "
    "programs. Add --json to a command to get JSON on stdout. `salli --help` and "
    "`salli <group> --help` describe the commands. Ids can be shortened to a unique prefix."
)
CLI_PIPE = (
    "Use the `salli` command-line tool through the Bash tool. Add --json to a command "
    "to get JSON on stdout (messages go to stderr); jq is available. When a step needs "
    "data from an earlier step, prefer to compose them in one Bash call (pipes, "
    "command substitution, jq) so that intermediate output does not have to pass "
    "through you. `salli --help` and `salli <group> --help` describe the commands. "
    "Ids can be shortened to a unique prefix."
)
WITH_SKILL = "\n\nsalli-core's agent skill for its CLI follows. `salli` is on PATH.\n\n" + SKILL
REFERENCE = (HERE / "cli_reference.md").read_text()
WITH_REF = (
    "\n\nThe reference below lists the commands that cover what you need and the JSON each "
    "returns; `salli` is on PATH.\n\n" + REFERENCE
)
_HELP = " `salli --help` and `salli <group> --help` describe the commands."
ARM_SYSTEM = {
    "mcp": "Use the Salli tools.",
    "cli-step": CLI_STEP + WITH_SKILL,
    "cli-pipe": CLI_PIPE + WITH_SKILL,
    "cli-pipe-noskill": CLI_PIPE,
    "cli-step-ref": CLI_STEP.replace(_HELP, "") + WITH_REF,
    "cli-pipe-ref": CLI_PIPE.replace(_HELP, "") + WITH_REF,
    "cli-pipe-skills": CLI_PIPE,
    "mcp-parity": "Use the Salli tools.",
}
MCP_SERVER = {"mcp": "mcp_stdio.py", "mcp-parity": "mcp_parity.py"}
# Arms whose skills are installed with `salli skills install --project` in the
# run's directory and discovered by Claude Code (Skill tool enabled), rather
# than pasted into the system prompt.
INSTALLED_SKILLS = {"cli-pipe-skills"}
# Step arms run under an allowlist: only `salli`, so pipes and other programs
# are refused. Composed arms cannot: Claude Code refuses to match commands that
# use shell variables, quoting, escapes or loops against an allowlist, which
# blocked 29 of 128 composed runs in the first pilot. They run with
# permissions bypassed instead, under a deny-list of destructive and network
# commands. Interpreters are allowed (agents write shell and Python loops over
# the CLI); only the salli executable is on PATH, so that code cannot import
# salli and go around the CLI. (Chain-task composed runs used an earlier list
# that also denied interpreters; it refused 4 calls in 256 runs.)
COMPOSED = {"cli-pipe", "cli-pipe-noskill", "cli-pipe-ref", "cli-pipe-skills"}
DENIED = [
    f"Bash({t}:*)" for t in (
        "rm", "rmdir", "mv", "cp", "dd", "chmod", "chown", "ln", "truncate", "shred",
        "curl", "wget", "nc", "ssh", "scp", "rsync", "git", "gh", "open", "osascript",
        "sudo", "kill", "pkill", "killall", "launchctl", "crontab",
        "uv", "pip", "npm", "brew", "docker", "supabase", "psql",
    )
]
ALLOWED = {
    "mcp": ["mcp__salli"],
    "mcp-parity": ["mcp__salli"],
    "cli-step": ["Bash(salli:*)"],
    "cli-step-ref": ["Bash(salli:*)"],
}
FIELDS = [
    "run_id", "task", "k", "size", "arm", "model", "rep", "success", "checks",
    "passes", "tool_calls", "tool_result_chars", "input_tokens", "cache_write_tokens",
    "cache_read_tokens", "output_tokens", "cost_usd", "duration_s", "num_turns",
    "denied", "is_error", "final",
]


def claude_cmd(arm: str, model: str, workdir: Path) -> list[str]:
    cmd = [
        CLAUDE, "-p", "--model", model,
        "--output-format", "stream-json", "--verbose",
        "--setting-sources", "project" if arm in INSTALLED_SKILLS else "",
        "--system-prompt", SYSTEM + ARM_SYSTEM[arm],
        "--exclude-dynamic-system-prompt-sections",
        "--no-session-persistence",
        "--strict-mcp-config", "--mcp-config", str(workdir / "mcp.json"),
        "--max-turns", "40",
    ]
    if arm in COMPOSED:
        cmd += ["--permission-mode", "bypassPermissions", "--disallowedTools", *DENIED]
    else:
        cmd += ["--allowedTools", *ALLOWED[arm]]
    if arm in MCP_SERVER:
        cmd += ["--tools", ""]
    elif arm in INSTALLED_SKILLS:
        cmd += ["--tools", "Bash", "Skill"]
    else:
        cmd += ["--tools", "Bash"]
    return cmd


HOME = str(Path.home())
INIT_DROP = ("skills", "plugins", "slash_commands", "terminal_slash_commands", "agents",
             "memory_paths", "scratchpad_path", "messaging_socket_path")


def scrub(lines: list[str]) -> list[str]:
    """Drop machine-specific fields from the init event and the home path everywhere."""
    out = []
    for line in lines:
        try:
            ev = json.loads(line)
            if ev.get("type") == "system" and ev.get("subtype") == "init":
                for k in INIT_DROP:
                    ev.pop(k, None)
                line = json.dumps(ev)
        except json.JSONDecodeError:
            pass
        line = line.replace(HOME, "~").replace(HOME.replace("/", "-"), "-HOME")
        out.append(line.replace(Path.home().name, "user"))
    return out


def parse_stream(lines: list[str]) -> dict:
    msgs: dict[str, dict] = {}
    calls, result_chars, denied, result = 0, 0, 0, {}
    for line in lines:
        try:
            ev = json.loads(line)
        except json.JSONDecodeError:
            continue
        if ev.get("type") == "assistant":
            m = ev["message"]
            msgs[m["id"]] = m.get("usage", {})
            calls += sum(1 for b in m.get("content", []) if b.get("type") == "tool_use")
        elif ev.get("type") == "user":
            for b in ev.get("message", {}).get("content", []):
                if isinstance(b, dict) and b.get("type") == "tool_result":
                    c = b.get("content")
                    text = c if isinstance(c, str) else json.dumps(c)
                    result_chars += len(text)
                    if b.get("is_error") and any(x in text.lower() for x in ("permission", "can't be checked", "denied")):
                        denied += 1
        elif ev.get("type") == "result":
            result = ev
    u = result.get("usage", {})
    return {
        "passes": len(msgs),
        "tool_calls": calls,
        "tool_result_chars": result_chars,
        "input_tokens": u.get("input_tokens", 0),
        "cache_write_tokens": u.get("cache_creation_input_tokens", 0),
        "cache_read_tokens": u.get("cache_read_input_tokens", 0),
        "output_tokens": u.get("output_tokens", 0),
        "cost_usd": result.get("total_cost_usd", 0),
        "num_turns": result.get("num_turns", 0),
        "is_error": result.get("is_error", True),
        "final": (result.get("result") or "").strip().splitlines()[-1:] or [""],
        "denied": denied,
    }


async def one_run(task: str, size: str, arm: str, model: str, rep: int, base_env: dict) -> dict:
    spec = TASKS[task]
    run_id = f"{task}-{size}-{arm}-{model}-{rep}-{uuid.uuid4().hex[:6]}"
    user = await make_user(size, SIZE_SEED[size])
    pre = await spec["pre"](user)
    workdir = WORK / run_id
    workdir.mkdir(parents=True)
    (workdir / "tmp").mkdir()
    # Own temp dir per run: parallel agents writing fixed names such as
    # $TMPDIR/acc.json overwrote each other's files in the first runs.
    env = {**base_env, "SALLI_USER_ID": user, "TMPDIR": str(workdir / "tmp")}
    (workdir / "mcp.json").write_text(json.dumps({"mcpServers": {"salli": {
        "command": str(SALLI / ".venv" / "bin" / "python"),
        "args": [str(HERE / MCP_SERVER.get(arm, "mcp_stdio.py"))],
        "env": {"SALLI_USER_ID": user, "SALLI": str(SALLI)},
    }} if arm in MCP_SERVER else {}}))
    if arm in INSTALLED_SKILLS:
        inst = await asyncio.create_subprocess_exec(
            str(SALLI / ".venv" / "bin" / "salli"), "skills", "install", "--project",
            cwd=workdir, env=env, stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.DEVNULL,
        )
        await inst.wait()
    t0 = time.time()
    proc = await asyncio.create_subprocess_exec(
        *claude_cmd(arm, model, workdir),
        cwd=workdir, env=env, stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        limit=1 << 26,  # stream-json lines can carry large tool results
    )
    proc.stdin.write(spec["prompt"].encode())
    await proc.stdin.drain()
    proc.stdin.close()
    stderr_task = asyncio.create_task(proc.stderr.read())

    lines: list[str] = []

    async def read_until_result() -> None:
        # Stop at the result event: Claude Code occasionally stays alive after
        # finishing (e.g. a child still holding the pipe), which once cost a
        # 15-minute timeout per run.
        async for raw in proc.stdout:
            line = raw.decode(errors="replace").rstrip("\n")
            lines.append(line)
            if line.startswith('{"type":"result"'):
                break

    try:
        await asyncio.wait_for(read_until_result(), timeout=900)
        err = b""
    except asyncio.TimeoutError:
        err = b"timeout"
    try:
        await asyncio.wait_for(proc.wait(), timeout=15)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()
    stderr_task.cancel()
    dur = time.time() - t0
    (OUT / "transcripts").mkdir(parents=True, exist_ok=True)
    with gzip.open(OUT / "transcripts" / f"{run_id}.jsonl.gz", "wt") as f:
        f.write("\n".join(scrub(lines)))
    m = parse_stream(lines)
    final = m.pop("final")[0]
    checks = await spec["check"](user, final, pre)
    success = all(v for k, v in checks.items() if isinstance(v, bool))
    shutil.rmtree(workdir, ignore_errors=True)
    row = {
        "run_id": run_id, "task": task, "k": spec["k"], "size": size, "arm": arm,
        "model": model, "rep": rep, "success": success, "checks": json.dumps(checks),
        "duration_s": round(dur, 1), "final": final[:200], **m,
    }
    if not lines:
        row["is_error"] = True
        row["final"] = err.decode(errors="replace")[:200]
    return row


def ensure_bin() -> None:
    link = HERE / "work" / "bin" / "salli"
    link.parent.mkdir(parents=True, exist_ok=True)
    if not link.exists():
        link.symlink_to(SALLI / ".venv" / "bin" / "salli")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="+", default=list(TASKS))
    ap.add_argument("--sizes", nargs="+", default=["small", "large"])
    ap.add_argument("--arms", nargs="+", default=list(ARM_SYSTEM))  # all arms
    ap.add_argument("--models", nargs="+", default=["haiku"])
    ap.add_argument("--reps", type=int, default=3)
    ap.add_argument("--jobs", type=int, default=4)
    ap.add_argument("--rerun", type=Path, help="file of run_ids to discard and run again")
    a = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    ensure_bin()
    base_env = {
        **os.environ, **salli_env(),
        "SALLI": str(SALLI),
        # Only the salli executable, not salli-core's environment, so code the
        # agent writes (shell or Python) can call the CLI but cannot import salli.
        "PATH": f"{HERE / 'work' / 'bin'}:{os.environ['PATH']}",
        "ENABLE_TOOL_SEARCH": "false",
        "DISABLE_AUTOUPDATER": "1",
    }
    base_env.pop("SALLI_USER_ID", None)
    if a.rerun:
        redo = set(a.rerun.read_text().split())
        with RUNS_CSV.open() as f:
            rows = list(csv.DictReader(f))
        sup = OUT / "superseded"
        (sup / "transcripts_shared_tmp").mkdir(parents=True, exist_ok=True)
        old = [r for r in rows if r["run_id"] in redo]
        with (sup / "runs_shared_tmp.csv").open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            if f.tell() == 0:
                w.writeheader()
            w.writerows(old)
        for r in old:
            t = OUT / "transcripts" / f"{r['run_id']}.jsonl.gz"
            if t.exists():
                shutil.move(str(t), sup / "transcripts_shared_tmp" / t.name)
        with RUNS_CSV.open("w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS)
            w.writeheader()
            w.writerows(r for r in rows if r["run_id"] not in redo)
        print(f"discarded {len(old)} runs for re-running", file=sys.stderr)
    done = set()
    if RUNS_CSV.exists():
        with RUNS_CSV.open() as f:
            done = {(r["task"], r["size"], r["arm"], r["model"], int(r["rep"])) for r in csv.DictReader(f)}
    jobs = [
        (t, s, arm, m, r)
        for r in range(1, a.reps + 1)
        for m in a.models for t in a.tasks for s in a.sizes for arm in a.arms
        if (t, s, arm, m, r) not in done
    ]
    print(f"{len(jobs)} runs to do ({len(done)} already recorded)", file=sys.stderr)
    sem = asyncio.Semaphore(a.jobs)
    new_file = not RUNS_CSV.exists()
    with RUNS_CSV.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()

        async def guarded(job):
            async with sem:
                try:
                    row = await one_run(*job, base_env)
                except Exception as exc:  # record and move on
                    print(f"FAILED {job}: {exc!r}", file=sys.stderr)
                    return
                w.writerow(row)
                f.flush()
                print(f"{row['run_id']}: success={row['success']} passes={row['passes']} "
                      f"cost=${row['cost_usd']:.4f} {row['checks']}", file=sys.stderr)

        await asyncio.gather(*(guarded(j) for j in jobs))


if __name__ == "__main__":
    asyncio.run(main())
