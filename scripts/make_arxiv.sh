#!/usr/bin/env bash
# Build the arXiv upload: main.tex, a fresh main.bbl, and every data file the
# paper reads (figures and tables are generated from data/). The archive is
# then compiled in a clean directory without bibtex, as arXiv will.
#
#   ./scripts/make_arxiv.sh        -> arxiv/cli-first-arxiv.tar.gz
set -euo pipefail
cd "$(dirname "$0")/.."
OUT=arxiv
STAGE="$OUT/stage"
rm -rf "$OUT" && mkdir -p "$STAGE" "$OUT/build"

# 1. Compile with intermediates kept, to get a .bbl that matches references.bib.
tectonic -X compile --keep-intermediates --outdir "$OUT/build" main.tex >/dev/null

# 2. Stage the sources.
cp main.tex "$STAGE/"
cp "$OUT/build/main.bbl" "$STAGE/"
grep -o -E '\{data/[^}]+\}' main.tex | tr -d '{}' | sort -u | while read -r f; do
  mkdir -p "$STAGE/$(dirname "$f")"
  cp "$f" "$STAGE/$f"
done

# 3. Test: compile the staged copy on its own, with no references.bib present.
(cd "$STAGE" && tectonic -X compile main.tex >/dev/null 2>&1) || { echo "staged build failed" >&2; exit 1; }
if pdftotext "$STAGE/main.pdf" - | grep -q '??'; then echo "unresolved references in staged build" >&2; exit 1; fi
rm -f "$STAGE/main.pdf"

# 4. Archive.
tar -czf "$OUT/cli-first-arxiv.tar.gz" -C "$STAGE" .
echo "arXiv archive: $OUT/cli-first-arxiv.tar.gz ($(tar -tzf "$OUT/cli-first-arxiv.tar.gz" | grep -vc '/$') files)"
