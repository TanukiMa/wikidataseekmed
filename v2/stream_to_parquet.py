#!/usr/bin/env python3
# Stream Wikidata latest-all.json.bz2 over HTTP and write minimal Parquet without jq
# Disk-minimal: no intermediate files, chunked network + decompression + JSON parse + Parquet write

import sys, json, argparse, bz2, codecs, time
from urllib.request import Request, urlopen
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path
from typing import Dict, Any, List

URL = "https://dumps.wikimedia.org/wikidatawiki/entities/latest-all.json.bz2"
UA = "wikidataseekmed/stream_to_parquet (https://github.com/; +local)"


def extract_objects_from_buffer(buf: str):
    """Yield complete top-level JSON object strings from buffer. Return remainder at end.
    The dump is a sequence like: [\n{...},\n{...},\n...\n]
    We parse by tracking curly-brace depth while respecting strings.
    """
    out = []
    i = 0
    n = len(buf)
    while i < n:
        # skip whitespace and separators at top level
        ch = buf[i]
        if ch.isspace() or ch in '[,]':
            i += 1
            continue
        if ch != '{':
            # Incomplete or unexpected; wait for more
            break
        start = i
        i += 1
        depth = 1
        in_str = False
        esc = False
        while i < n:
            c = buf[i]
            if in_str:
                if esc:
                    esc = False
                elif c == '\\':
                    esc = True
                elif c == '"':
                    in_str = False
            else:
                if c == '"':
                    in_str = True
                elif c == '{':
                    depth += 1
                elif c == '}':
                    depth -= 1
                    if depth == 0:
                        i += 1
                        out.append(buf[start:i])
                        break
            i += 1
        else:
            # need more data
            break
    remainder = buf[i:]
    return out, remainder


def keep_entity(o: Dict[str, Any]) -> bool:
    labels = o.get('labels', {})
    if 'en' in labels or 'ja' in labels:
        return True
    claims = o.get('claims', {})
    for pid in ("P31", "P279", "P486", "P494", "P493", "P5806", "P2892"):
        if pid in claims:
            return True
    return False


def values_from_claims(claims: Dict[str, Any], pid: str, entity: bool) -> List[str]:
    out: List[str] = []
    for cl in claims.get(pid, []) or []:
        if cl.get('rank') == 'deprecated':
            continue
        snak = cl.get('mainsnak', {})
        if snak.get('snaktype') != 'value':
            continue
        dv = snak.get('datavalue', {})
        v = dv.get('value')
        if entity and isinstance(v, dict):
            vid = v.get('id')
            if vid:
                out.append(str(vid))
        elif not entity and v is not None:
            out.append(str(v))
    # dedup while preserving order
    seen = set()
    dedup = []
    for x in out:
        if x not in seen:
            seen.add(x)
            dedup.append(x)
    return dedup


def main():
    ap = argparse.ArgumentParser(description='Stream Wikidata dump to Parquet (Python-only)')
    ap.add_argument('--output', required=True, help='Output Parquet path')
    ap.add_argument('--chunk-size', type=int, default=20000, help='Rows per Parquet write batch')
    ap.add_argument('--url', default=URL, help='Dump URL')
    args = ap.parse_args()

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    # buffers
    buf = ''
    decoder = codecs.getincrementaldecoder('utf-8')()
    decomp = bz2.BZ2Decompressor()

    # parquet writer
    writer = None
    batch_rows = 0
    cols = {
        'id': [],
        'label_en': [], 'label_ja': [],
        'desc_en': [], 'desc_ja': [],
        'P31': [], 'P279': [],
        'mesh': [], 'icd10': [], 'icd9': [], 'snomed': [], 'umls': []
    }

    def flush():
        nonlocal writer
        if not cols['id']:
            return
        arrays = {
            'id': pa.array(cols['id'], type=pa.string()),
            'label_en': pa.array(cols['label_en'], type=pa.string()),
            'label_ja': pa.array(cols['label_ja'], type=pa.string()),
            'desc_en': pa.array(cols['desc_en'], type=pa.string()),
            'desc_ja': pa.array(cols['desc_ja'], type=pa.string()),
            'P31': pa.array(cols['P31'], type=pa.list_(pa.string())),
            'P279': pa.array(cols['P279'], type=pa.list_(pa.string())),
            'mesh': pa.array(cols['mesh'], type=pa.list_(pa.string())),
            'icd10': pa.array(cols['icd10'], type=pa.list_(pa.string())),
            'icd9': pa.array(cols['icd9'], type=pa.list_(pa.string())),
            'snomed': pa.array(cols['snomed'], type=pa.list_(pa.string())),
            'umls': pa.array(cols['umls'], type=pa.list_(pa.string())),
        }
        table = pa.Table.from_pydict(arrays)
        if writer is None:
            writer = pq.ParquetWriter(out, table.schema, compression='snappy')
        writer.write_table(table)
        for k in cols:
            cols[k].clear()

    req = Request(args.url, headers={'User-Agent': UA})
    with urlopen(req) as resp:
        t0 = time.time(); bytes_in = 0; last_log = 0; total_rows = 0
        CHUNK = 1024 * 1024  # 1MB
        while True:
            chunk = resp.read(CHUNK)
            if not chunk:
                break
            bytes_in += len(chunk)
            now = time.time()
            if now - last_log >= 5:
                mb = bytes_in / (1024*1024)
                elapsed = now - t0
                rate = mb / elapsed if elapsed > 0 else 0
                print(f"[download] {mb:,.1f} MiB in {elapsed:,.0f}s ({rate:,.2f} MiB/s)", file=sys.stderr)
                last_log = now
            try:
                decomp_bytes = decomp.decompress(chunk)
            except Exception as e:
                # Corruption or premature close
                print(f"Decompress error: {e}", file=sys.stderr)
                break
            if not decomp_bytes:
                continue
            text = decoder.decode(decomp_bytes)
            if text:
                buf += text
            objs, buf = extract_objects_from_buffer(buf)
            for obj_s in objs:
                try:
                    o = json.loads(obj_s)
                except Exception:
                    continue
                if not keep_entity(o):
                    continue
                labels = o.get('labels', {})
                descs = o.get('descriptions', {})
                claims = o.get('claims', {})
                cols['id'].append(o.get('id'))
                cols['label_en'].append(labels.get('en', {}).get('value', ''))
                cols['label_ja'].append(labels.get('ja', {}).get('value', ''))
                cols['desc_en'].append(descs.get('en', {}).get('value', ''))
                cols['desc_ja'].append(descs.get('ja', {}).get('value', ''))
                cols['P31'].append(values_from_claims(claims, 'P31', entity=True))
                cols['P279'].append(values_from_claims(claims, 'P279', entity=True))
                cols['mesh'].append(values_from_claims(claims, 'P486', entity=False))
                cols['icd10'].append(values_from_claims(claims, 'P494', entity=False))
                cols['icd9'].append(values_from_claims(claims, 'P493', entity=False))
                cols['snomed'].append(values_from_claims(claims, 'P5806', entity=False))
                cols['umls'].append(values_from_claims(claims, 'P2892', entity=False))
                batch_rows += 1
                total_rows += 1
                if batch_rows % args.chunk_size == 0:
                    flush()
                    print(f"[parquet] wrote {total_rows:,} rows", file=sys.stderr)
        # flush decoder remainder
        rem = decoder.decode(b'', final=True)
        if rem:
            buf += rem
        objs, buf = extract_objects_from_buffer(buf)
        for obj_s in objs:
            try:
                o = json.loads(obj_s)
            except Exception:
                continue
            if not keep_entity(o):
                continue
            labels = o.get('labels', {})
            descs = o.get('descriptions', {})
            claims = o.get('claims', {})
            cols['id'].append(o.get('id'))
            cols['label_en'].append(labels.get('en', {}).get('value', ''))
            cols['label_ja'].append(labels.get('ja', {}).get('value', ''))
            cols['desc_en'].append(descs.get('en', {}).get('value', ''))
            cols['desc_ja'].append(descs.get('ja', {}).get('value', ''))
            cols['P31'].append(values_from_claims(claims, 'P31', entity=True))
            cols['P279'].append(values_from_claims(claims, 'P279', entity=True))
            cols['mesh'].append(values_from_claims(claims, 'P486', entity=False))
            cols['icd10'].append(values_from_claims(claims, 'P494', entity=False))
            cols['icd9'].append(values_from_claims(claims, 'P493', entity=False))
            cols['snomed'].append(values_from_claims(claims, 'P5806', entity=False))
            cols['umls'].append(values_from_claims(claims, 'P2892', entity=False))
        flush()
        if writer is not None:
            writer.close()
    print(f"Saved Parquet: {out}")
    print("[done] Parquet written", file=sys.stderr)


if __name__ == '__main__':
    main()
