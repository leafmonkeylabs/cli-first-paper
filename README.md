# CLI-First: What an Agent Knows About an Interface Matters More Than Its Protocol

Chandra Irugalbandara, Leaf Monkey Labs.

This repository holds the paper and everything behind it: the LaTeX source and PDF, plus the data, harness and analysis for the exploratory experiment (Section 6) and the case-study measurements (Section 4).

## The paper

`main.pdf` is the current version. To build it from source:

```bash
tectonic -X compile main.tex      # or: ./scripts/make_arxiv.sh for the arXiv archive
```

It is written in ACM `acmart` (sigconf, `nonacm`). The tables and figures are read from `data/` when the PDF is built, so a rebuild after re-running the analysis picks up the new numbers.

Every number, table and figure dataset in the paper's experiment section is produced by `pilot/stats.py` from `data/pilot/runs.csv` and the transcripts. Nothing was edited by hand.

## Contents

| Path | What it is |
|---|---|
| `data/pilot/runs.csv` | The 704 retained runs: task, ledger size, configuration, model, success, tokens by type, cost, passes, tool calls, time |
| `data/pilot/transcripts/` | One gzipped stream-JSON transcript per retained run, named `<task>-<size>-<arm>-<model>-<rep>-<id>` |
| `data/pilot/superseded/` | The 243 superseded runs and their transcripts, grouped by the reason they were superseded |
| `data/pilot/run_ledger.csv` | All 947 attempted runs, with wave, parallelism, permissions and fate |
| `data/pilot/logs/` | The collection logs of the five waves |
| `data/pilot/*.csv`, `*.tex` | Analysis outputs: ratios and intervals, per-task ratios, interaction, sensitivity, success, mechanism, behaviour, oversight, and the table rows the paper reads |
| `pilot/run.py` | The harness: runs one task through one configuration with Claude Code in headless mode |
| `pilot/tasks.py`, `pilot/seed.py` | The six tasks, their database checks, and the seeded small and large ledgers |
| `pilot/mcp_stdio.py`, `pilot/mcp_parity.py` | The curated MCP server's stdio wrapper (MCP-24) and the server generated from the CLI (MCP-102) |
| `pilot/cli_reference.py`, `pilot/cli_reference.md` | The command-sheet generator and the sheet used in the runs |
| `pilot/analyze.py`, `pilot/stats.py`, `pilot/ledger.py`, `pilot/oversight.py` | Run parsing, statistics, the run ledger and the oversight measures |
| `main.tex`, `references.bib`, `main.bbl`, `main.pdf` | The paper |
| `scripts/` | Case-study measurements (coverage, agent trailers, feature timeline, interface tokens), the cost-model table, and the arXiv build |
| `data/*.csv`, `data/*.json`, `data/*.txt` | Case-study outputs |

Configuration names in files differ from the paper's:

| File | Paper |
|---|---|
| `mcp` | MCP-24 |
| `mcp-parity` | MCP-102 |
| `cli-step` | CLI skill/step |
| `cli-pipe` | CLI skill/comp |
| `cli-pipe-noskill` | CLI help/comp |
| `cli-pipe-skills` | CLI installed/comp |
| `cli-step-ref` | CLI sheet/step |
| `cli-pipe-ref` | CLI sheet/comp |

Task names: `T1`, `T2`, `T4` and `T8` are the chains with k = 1, 2, 4 and 8. `L1` is bulk entry and `L2` is fan-out.

## Re-running the analysis

Python 3.11 or later, standard library only:

```bash
python3 pilot/stats.py      # ratios, intervals, tests, tables -> data/pilot/
python3 pilot/ledger.py     # run ledger
python3 pilot/oversight.py  # write-output discarding in composed runs
```

The permutation tests and bootstrap use a fixed seed, so outputs are identical across runs.

## Re-running the experiment

You need:
- salli-core (https://github.com/leafmonkeylabs/salli-core) at commit `0277747`, set up as its README describes, with a local Supabase stack;
- Claude Code 2.1.293;
- an Anthropic API key.

Point `SALLI` at the checkout and run the harness with that checkout's interpreter:

```bash
SALLI=/path/to/salli-core $SALLI/.venv/bin/python pilot/run.py --models haiku sonnet --reps 3 --jobs 1
```

Run it against a local test instance only. The composed configurations run with Claude Code's permissions bypassed under a deny-list and **without a sandbox**, and the agent's environment holds the instance's database URL and service keys. Use a container or a disposable machine.

Model behaviour and prices change, so expect a re-run to differ in absolute cost. The paper's prices are in Section 6.3.

## Case-study scripts

`scripts/reproduce.sh` regenerates the Section 4 measurements from a pinned snapshot (`84a7d1e`) of Salli's development history. That history predates the open-source core and is private, so these scripts cannot be re-run outside Leaf Monkey Labs. Their outputs are included in `data/`.

## Redactions

The harness replaced the operator's home directory and username in transcripts and logs. Where Claude Code's output truncation had cut a home-directory path partway through the username, the fragment was later replaced with `~` by hand (four transcripts). Two transcripts, `L1-large-cli-pipe-skills-sonnet-1-b4b7e3` and `L1-small-cli-pipe-skills-sonnet-2-5bedf8`, had a wildcard read in the system temp directory pick up files written by unrelated processes on the host. Those tool results, and the agent's text that echoed them, are replaced with a note. Nothing else was altered.

## Licence

Code (`pilot/`, `scripts/`) is under the MIT licence (`LICENSE-CODE`). The paper, data and documentation (`main.*`, `references.bib`, `data/`, this README) are under CC BY 4.0 (`LICENSE-DATA`). Please cite the paper; `CITATION.cff` has the details.
