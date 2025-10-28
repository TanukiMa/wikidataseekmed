#!/usr/bin/env bash
set -euo pipefail
# Created: 2025-10-28T01:50:27Z

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
V2_DIR="$ROOT_DIR/v2"
RAW_DIR="$V2_DIR/raw"
WORK_DIR="$V2_DIR/work"
OUT_DIR="$V2_DIR/parquet"
LOG_DIR="$V2_DIR/logs"

URL="https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"
NDJSON_GZ="$WORK_DIR/filtered.ndjson.gz"
PARQUET="$OUT_DIR/wikidata_min.parquet"


# Create a writable temp dir (prefer TMPDIR, fallback to /tmp, caches, repo)
TMPRUN=""
for cand in "${TMPDIR:-}" /tmp "$HOME/Library/Caches" "$HOME/.cache" "$V2_DIR"; do
  [ -z "$cand" ] && continue
  if mkdir -p "$cand" 2>/dev/null && [ -w "$cand" ]; then
    TMPRUN="$(mktemp -d "$cand/wikidataseekmed.XXXXXXXX" 2>/dev/null || mktemp -d -t wikidataseekmed)" || true
    if [ -n "$TMPRUN" ] && [ -d "$TMPRUN" ] && [ -w "$TMPRUN" ]; then
      break
    fi
  fi
  TMPRUN=""
done
if [ -z "$TMPRUN" ]; then
  echo "No writable temp directory found" >&2
  exit 1
fi
PARQUET_TMP="$TMPRUN/wikidata_min.parquet"
trap 'rm -rf "$TMPRUN"' EXIT

mkdir -p "$RAW_DIR" "$WORK_DIR" "$OUT_DIR" "$LOG_DIR"

echo "[1/4] Download + Python-only filtering + direct Parquet (low disk)"
python3 "$V2_DIR/stream_to_parquet.py" --output "$PARQUET_TMP" --chunk-size 20000 && mv -f "$PARQUET_TMP" "$PARQUET"

echo "[2/4] Show Parquet schema/sample"
python3 - <<PY
import pandas as pd
p="$PARQUET"
df=pd.read_parquet(p)
print("Rows:", len(df))
print(df.head(3).to_string(index=False))
PY

if [ ! -f "$PARQUET" ]; then
  echo "Parquet not created. Aborting." >&2
  exit 1
fi

echo "[3/4] Show Parquet schema/sample"
python3 - <<PY
import pandas as pd
import sys
p="$PARQUET"
df=pd.read_parquet(p)
print("Rows:", len(df))
print(df.head(3).to_string(index=False))
PY

echo "[4/4] Run existing tools (using network SPARQL; local Parquet is prepared for future local backends)"
cd "$ROOT_DIR"
# Example runs; adjust arguments as needed
python3 wikidata_category_finder.py --exact "疫学" || true
python3 wikidataseekmed_improved.py --small --limit 2000 --log "$LOG_DIR/small.log" || true

echo "Done. Parquet at: $PARQUET"