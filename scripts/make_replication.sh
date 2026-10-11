#!/usr/bin/env bash
# Build the public repository's tree from committed files only: the paper
# (main.tex, references.bib, main.bbl, main.pdf), pilot/, scripts/ and data/,
# plus replication/'s README, licences and metadata. Reviews and this
# repository's history are never included.
#
#   ./scripts/make_replication.sh [OUT]   (default: ../cli-first-public)
set -euo pipefail
cd "$(dirname "$0")/.."
OUT="${1:-../cli-first-public}"
[ -e "$OUT" ] && { echo "$OUT exists; remove it first" >&2; exit 1; }
mkdir -p "$OUT"
git archive HEAD main.tex references.bib main.bbl main.pdf pilot scripts data | tar -x -C "$OUT"
cp replication/README.md replication/LICENSE-CODE replication/LICENSE-DATA replication/CITATION.cff replication/.zenodo.json "$OUT/"
printf '__pycache__/\npilot/work/\narxiv/\n*.aux\n*.log\n*.out\n*.blg\n!data/pilot/logs/*.log\n!data/pilot-ablation/logs/*.log\n!data/pilot-v2/logs/*.log\n!data/pilot-iso/logs/*.log\n' > "$OUT/.gitignore"
echo "replication package: $OUT ($(find "$OUT" -type f | wc -l | tr -d ' ') files, $(du -sh "$OUT" | cut -f1))"
