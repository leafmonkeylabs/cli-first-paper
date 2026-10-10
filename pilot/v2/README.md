# Experiment 1 (v2): the pilot re-run on the rewritten core

The paper's interface experiment (`pilot/`, salli-core `0277747`) ported to the rewritten
salli-core, pinned at **`1322f84`**. The same six tasks (T1, T2, T4, T8, L1, L2) on the
same seeded ledgers (small and large: same accounts, entries and amounts), through the
new core's interfaces. Nothing in `pilot/*.py`, `data/` or `scripts/` is changed;
everything here is new.

| File | What |
|---|---|
| `run.py` | the harness: `pilot/run.py` with the v2 changes marked `v2:` |
| `seed.py` | `pilot/seed.py` plus what the new core needs to make the same ledger; `make_pat` |
| `tasks.py` | a copy of `pilot/tasks.py` (prompts and checks unchanged) |
| `mcp_stdio.py` | the core's own MCP server over stdio, as `SALLI_USER_ID` |
| `salli_env.py` | loads the v2 checkout's `.env`; the server URL and the CLI's path |
| `cli_reference.py` → `cli_reference.md` | the command sheet for the `*-ref` arms |
| `equivalence.py` | scripted right and wrong solutions of every task through MCP and the CLI, then the checks (no agent) |

## Arms

| Arm | Interface | Knowledge | Calls |
|---|---|---|---|
| `mcp` | the core's MCP server (46 tools at `1322f84`) | tool schemas | tools only |
| `cli-pipe-noskill` | `salli` (TypeScript CLI) | `--help` | composed |
| `cli-pipe` | `salli` | the CLI's agent skill (`packages/cli/skills/salli-cli`) in the prompt | composed |
| `cli-step-ref` | `salli` | the command sheet | one command per call (`Bash(salli:*)`) |
| `cli-pipe-ref` | `salli` | the command sheet | composed |

## The stack

Everything lives in `pilot/work/` (git-ignored). The checkout is
`pilot/work/salli-core-v2`, with its own Supabase project, **`salli-pilot-v2`**, on ports
556xx (API 55621, DB 55622, shadow 55620, pooler 55629, studio 55623, inbucket 55624,
analytics 55627, edge inspector 55683), so it can't collide with `salli-pilot` (553xx) or
any other stack.

```bash
# once
git clone https://github.com/leafmonkeylabs/salli-core pilot/work/salli-core-v2
cd pilot/work/salli-core-v2 && git checkout 1322f84
#   supabase/config.toml: project_id = "salli-pilot-v2", every port 556xx (see above)
uv sync && npm ci && npm run build          # the CLI: packages/cli/dist/salli.js (Node >= 22.12)
supabase start -x studio,storage-api,imgproxy,realtime,edge-runtime,logflare,vector,postgres-meta,mailpit,supavisor,postgrest
uv run salli-server setup --email pilot-v2@salli.test --currency LKR --tax-residency LK \
    --skip-llm-key --income employment,freelance,rental,interest
#   (asks for a password; the one used is in pilot/work/pilot-v2-credentials.env)
```

Run every `supabase` command from `pilot/work/salli-core-v2`, so it acts on
`salli-pilot-v2` only: `supabase status`, `supabase stop` (keeps the data).

### The API server

The CLI arms talk to the API server over HTTP. It runs from the v2 checkout, bound to
127.0.0.1, on port **55680** (8765 was already taken by another session's server;
`SALLI_SERVER` overrides the URL the harness uses).

```bash
# start (from the repo root)
cd pilot/work/salli-core-v2 && nohup .venv/bin/salli-server serve --host 127.0.0.1 --port 55680 \
    > ../v2-server.log 2>&1 & echo $! > ../v2-server.pid; cd -
curl -s http://127.0.0.1:55680/v1/meta     # check
# stop
kill "$(cat pilot/work/v2-server.pid)"     # or: lsof -tiTCP:55680 -sTCP:LISTEN | xargs kill
```

## Running

With the v2 checkout's interpreter, from the repo root:

```bash
P=pilot/work/salli-core-v2/.venv/bin/python
CLAUDE="$HOME/Library/Application Support/Claude/claude-code/2.1.293/8433d0d9cd0d/claude.app/Contents/MacOS/claude"
$P pilot/v2/cli_reference.py > pilot/v2/cli_reference.md     # the sheet (needs the server)
$P pilot/v2/equivalence.py small large                        # tasks through both surfaces, no agent
# the rewrite waves as collected (resume from data/pilot-v2/runs.csv): Haiku x5 then Sonnet x3,
# --jobs 4, while the ablation wave (pilot/run.py, --jobs 6) ran on the same machine
CLAUDE_BIN="$CLAUDE" $P pilot/v2/run.py --models haiku --reps 5 --jobs 4
CLAUDE_BIN="$CLAUDE" $P pilot/v2/run.py --models sonnet --reps 3 --jobs 4
# the isolation wave (paper Section 7.3): in-wave references plus MCP-24's tools only and
# the CLI addressing accounts by id only; Haiku then Sonnet, --jobs 4, nothing else running
PILOT_OUT=data/pilot-iso CLAUDE_BIN="$CLAUDE" $P pilot/v2/run.py --arms mcp mcp-24 cli-pipe-ref cli-pipe-ref-ids --models haiku --reps 5 --jobs 4
PILOT_OUT=data/pilot-iso CLAUDE_BIN="$CLAUDE" $P pilot/v2/run.py --arms mcp mcp-24 cli-pipe-ref cli-pipe-ref-ids --models sonnet --reps 3 --jobs 4
```

Output goes to `data/pilot-v2/` (`runs.csv`, `transcripts/`) unless `PILOT_OUT` names
another directory; the smoke tests used `PILOT_OUT=pilot/work/v2-smoke/...`.
`--arms`, `--tasks` and `--sizes` narrow a run.

## What changed from `pilot/run.py`, and why

Kept identical: the system prompt, each arm's instructions (less one sentence, below),
the permissions model (`--allowedTools Bash(salli:*)` for the step arm,
`bypassPermissions` plus the same deny-list for composed arms, `mcp__salli` with no
other tools for MCP), `--setting-sources ""`, `--max-turns 40`, a TMPDIR per run, a bin
dir holding only `salli` ahead of `PATH`, stream parsing, token accounting, `scrub()`,
and the `runs.csv` columns.

- **The CLI is a client of the API server.** `salli` is a wrapper in a bin dir per arm
  (`pilot/work/v2-bin/<arm>/salli`) that execs `node packages/cli/dist/salli.js`. Each
  run's fresh user gets a personal access token from the core's token service; it reaches
  the CLI as `SALLI_TOKEN` (with `SALLI_SERVER`) in the CLI arms' environment only, and is
  revoked after the run. `SALLI_CONFIG_DIR` is the run's own directory, so the CLI never
  reads or writes `~/.config/salli`.
- **Scrubbing.** The run's token and the server URL (and its host:port) are replaced with
  placeholders in the saved transcript, besides the home path.
- **"Ids can be shortened to a unique prefix."** is kept in the CLI prompts and the sheet header, exactly as in the paper. At `1322f84` the docs (root README, CLI README, skill) still promise it, and `entries add` accepts an account id prefix, so the sentence is now true. That makes this re-run a test of principle P5 (a sheet that matches behaviour).
- **The skill** comes from `packages/cli/skills/salli-cli/SKILL.md`.
- **Arms.** Only the five above; `cli-step`, `cli-pipe-skills`, `mcp-parity` and the
  sheet ablations are not ported. `--rerun` is dropped.
- **Seeding** (`seed.py`): a new user names its base currency (LKR) and tax residency
  (LK) — with no residency the new core assumes no country, computes no tax and leaves the
  Sri Lankan tax accounts out of the starter chart — and the starter chart's
  "Bank Account" (1200) is renamed to the old "Bank Account (LKR)". The result is the old
  chart: 13 starter accounts with the same codes, names, types and tax roles, plus the
  debts' liability accounts (16 small, 106 large), 30 / 440 entries, tax LKR 388,500.

## Isolation wave (paper Section 7.3)

Two configurations separate the rewrite's changes on each side:
- **`mcp-24`** is the 1322f84 MCP server serving only the 24 tools that made up the paper's MCP-24 at 0277747 (`mcp24.py`; `mcp_stdio.py` removes the others when `SALLI_MCP_TOOLS` is set). Their definitions are 3,122 o200k tokens, against 6,599 for all 46.
- **`cli-pipe-ref-ids`** is the composed CLI with the sheet, but accounts are addressed by id only, as MCP's tools require. `sheet_ids.py` documents account arguments as ids, and the `salli` wrapper refuses account codes and names in `--debit`, `--credit` and `--parent` with a plain error. It emulates a CLI without code/name addressing; the product itself was not changed.

The wave re-runs `mcp` (MCP-46) and `cli-pipe-ref` as in-wave references.

Changes to the harness from this wave on, none visible to the agents except as noted:
- **No .env in the agents' environment.** The server's `.env` (database URL, service keys) is no longer put there. The TypeScript CLI needs only its token, and the MCP server loads the `.env` itself. Earlier waves passed it, as `pilot/run.py` had to for the in-process Python CLI. No agent in any wave read the environment (`pilot/followup_mechanisms.py`, host reach).
- **Token revocation in a `finally` block.** The run's token is revoked even if the run errors.
- **Recorded run times.** Start and end per run go to `run_times.csv` for the ledger (`pilot/followup_ledger.py`).
- **Scrubbed final line.** The `final` column is scrubbed like the transcripts.

## Collection conditions (all follow-up waves)

`data/followup/run_ledger.csv` lists every follow-up run with its wave, configured `--jobs`, start, end and the number of follow-up runs in progress at its midpoint. The ablation and rewrite waves overlapped on one machine, with a median of 6–10 agents at once, so their timings are not comparable across configurations. The isolation wave ran alone at `--jobs 4`. No follow-up run was discarded or re-collected.
