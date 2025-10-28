#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
V2_DIR="$ROOT_DIR/v2"
RAW_DIR="$V2_DIR/raw"
WORK_DIR="$V2_DIR/work"
OUT_DIR="$V2_DIR/parquet"
LOG_DIR="$V2_DIR/logs"

URL="https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"
RAW_BZ2="$RAW_DIR/latest-all.json.bz2"
NDJSON_GZ="$WORK_DIR/filtered.ndjson.gz"
PARQUET="$OUT_DIR/wikidata_min.parquet"

mkdir -p "$RAW_DIR" "$WORK_DIR" "$OUT_DIR" "$LOG_DIR"

command -v aria2c >/dev/null 2>&1 || { echo "aria2c not found. Install: brew install aria2 (macOS) or apt install aria2" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq not found. Install: brew install jq or apt install jq" >&2; exit 1; }

# 1) Fast multi-connection download
echo "[1/5] Download with aria2c (multi-connection) -> $RAW_BZ2"
aria2c -x16 -s16 -k1M -c -o "$(basename "$RAW_BZ2")" -d "$RAW_DIR" "$URL"

# 2) Filter needed fields into NDJSON.gz
echo "[2/5] Filter (decompress + jq) -> NDJSON (gz)"
(bunzip2 -c "$RAW_BZ2" || bzip2 -dc "$RAW_BZ2") \
| jq -c '
  select(
    (.labels.en or .labels.ja)
    or (.claims|has("P31") or has("P279") or has("P486") or has("P494") or has("P493") or has("P5806") or has("P2892"))
  )
  | {
    id,
    l:{en:(.labels.en.value // ""), ja:(.labels.ja.value // "")},
    d:{en:(.descriptions.en.value // ""), ja:(.descriptions.ja.value // "")},
    P31: ([.claims.P31[]?  | select(.rank!="deprecated") | .mainsnak.datavalue.value.id] | unique),
    P279: ([.claims.P279[]? | select(.rank!="deprecated") | .mainsnak.datavalue.value.id] | unique),
    ext:{
      mesh:   ([.claims.P486[]?  | .mainsnak.datavalue.value] | unique),
      icd10:  ([.claims.P494[]?  | .mainsnak.datavalue.value] | unique),
      icd9:   ([.claims.P493[]?  | .mainsnak.datavalue.value] | unique),
      snomed: ([.claims.P5806[]? | .mainsnak.datavalue.value] | unique),
      umls:   ([.claims.P2892[]? | .mainsnak.datavalue.value] | unique)
    }
  }' \
| gzip -c > "$NDJSON_GZ"

# 3) Convert to Parquet
echo "[3/5] Convert NDJSON (gz) -> Parquet"
python3 "$V2_DIR/ndjson_to_parquet.py" --input "$NDJSON_GZ" --output "$PARQUET"

# 4) Show sample
echo "[4/5] Show Parquet schema/sample"
python3 - <<PY
import pandas as pd
p="$PARQUET"
df=pd.read_parquet(p)
print("Rows:", len(df))
print(df.head(3).to_string(index=False))
PY

# 5) Run existing tools (still WDQS online)
echo "[5/5] Run existing tools"
cd "$ROOT_DIR"
python3 wikidata_category_finder.py --exact "疫学" || true
python3 wikidataseekmed_improved.py --small --limit 2000 --log "$LOG_DIR/small_aria2c.log" || true

echo "Done. Parquet at: $PARQUET"