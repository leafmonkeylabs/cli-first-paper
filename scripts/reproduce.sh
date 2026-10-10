#!/usr/bin/env bash
# Regenerate every number and figure dataset in the paper, from pinned snapshots.
# Only git objects are read; working trees are never touched.
# Override the path with: SALLI=... ./scripts/reproduce.sh
set -euo pipefail
cd "$(dirname "$0")"
SALLI="${SALLI:?set SALLI to a checkout of Salli (leafmonkeylabs/salli, private)}"
SALLI_REF="84a7d1e"    # leafmonkeylabs/salli main, 2026-09-13 (paper snapshot)
mkdir -p ../data

python3 coverage_salli.py --repo "$SALLI" --ref "$SALLI_REF" > ../data/salli_coverage.csv
python3 feature_timeline_salli.py --repo "$SALLI" --ref "$SALLI_REF" > ../data/salli_feature_timeline.csv
python3 cost_model.py > ../data/cost_model.csv

{
  echo "salli all:            $(python3 agent_trailers.py --repo "$SALLI" --ref "$SALLI_REF")"
} > ../data/agent_trailers.txt

# Interface-token measurement needs Salli's Python environment at the snapshot.
EXPORT="$(mktemp -d)"
git -C "$SALLI" archive "$SALLI_REF" | tar -x -C "$EXPORT"
(cd "$EXPORT" && uv sync -q)
uv run --project "$EXPORT" --with tiktoken python measure_interface_tokens.py > ../data/salli_interface_tokens.json
rm -rf "$EXPORT"
echo "done: see ../data/"
