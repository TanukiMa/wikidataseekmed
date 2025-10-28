#!/usr/bin/env python3
import sys, json, argparse
import pyarrow as pa
import pyarrow.parquet as pq
from pathlib import Path

def as_list_str(v):
    if v is None:
        return []
    if isinstance(v, list):
        return [str(x) for x in v]
    return [str(v)]

def main():
    ap = argparse.ArgumentParser(description='Read NDJSON from stdin and write Parquet incrementally')
    ap.add_argument('--output', required=True, help='Output Parquet file path')
    ap.add_argument('--chunk-size', type=int, default=50000, help='Rows per batch to write')
    args = ap.parse_args()

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    buffer = {
        'id': [],
        'label_en': [], 'label_ja': [],
        'desc_en': [],  'desc_ja': [],
        'P31': [], 'P279': [],
        'mesh': [], 'icd10': [], 'icd9': [], 'snomed': [], 'umls': []
    }

    writer = None
    rows = 0

    def flush():
        nonlocal writer
        if len(buffer['id']) == 0:
            return
        arrays = {
            'id': pa.array(buffer['id'], type=pa.string()),
            'label_en': pa.array(buffer['label_en'], type=pa.string()),
            'label_ja': pa.array(buffer['label_ja'], type=pa.string()),
            'desc_en': pa.array(buffer['desc_en'], type=pa.string()),
            'desc_ja': pa.array(buffer['desc_ja'], type=pa.string()),
            'P31': pa.array(buffer['P31'], type=pa.list_(pa.string())),
            'P279': pa.array(buffer['P279'], type=pa.list_(pa.string())),
            'mesh': pa.array(buffer['mesh'], type=pa.list_(pa.string())),
            'icd10': pa.array(buffer['icd10'], type=pa.list_(pa.string())),
            'icd9': pa.array(buffer['icd9'], type=pa.list_(pa.string())),
            'snomed': pa.array(buffer['snomed'], type=pa.list_(pa.string())),
            'umls': pa.array(buffer['umls'], type=pa.list_(pa.string())),
        }
        table = pa.Table.from_pydict(arrays)
        if writer is None:
            writer = pq.ParquetWriter(out_path, table.schema, compression='snappy')
        writer.write_table(table)
        # clear buffers
        for k in buffer:
            buffer[k].clear()

    for line in sys.stdin:
        try:
            o = json.loads(line)
        except Exception:
            continue
        L = o.get('l', {})
        D = o.get('d', {})
        E = o.get('ext', {})
        buffer['id'].append(o.get('id'))
        buffer['label_en'].append(L.get('en', ''))
        buffer['label_ja'].append(L.get('ja', ''))
        buffer['desc_en'].append(D.get('en', ''))
        buffer['desc_ja'].append(D.get('ja', ''))
        buffer['P31'].append(as_list_str(o.get('P31') or []))
        buffer['P279'].append(as_list_str(o.get('P279') or []))
        buffer['mesh'].append(as_list_str(E.get('mesh') or []))
        buffer['icd10'].append(as_list_str(E.get('icd10') or []))
        buffer['icd9'].append(as_list_str(E.get('icd9') or []))
        buffer['snomed'].append(as_list_str(E.get('snomed') or []))
        buffer['umls'].append(as_list_str(E.get('umls') or []))
        rows += 1
        if rows % args.chunk-size == 0:
            flush()

    flush()
    if writer is not None:
        writer.close()
    print(f"Saved Parquet: {out_path}")

if __name__ == '__main__':
    main()
