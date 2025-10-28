#!/usr/bin/env python3
import argparse, gzip, json
import pandas as pd
from pathlib import Path

def main():
    ap = argparse.ArgumentParser(description='Convert filtered NDJSON.gz to Parquet')
    ap.add_argument('--input', required=True, help='filtered.ndjson.gz path')
    ap.add_argument('--output', required=True, help='output parquet path')
    args = ap.parse_args()

    inp = Path(args.input)
    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)

    ids=[]; le=[]; lj=[]; de=[]; dj=[]; p31=[]; p279=[]; mesh=[]; icd10=[]; icd9=[]; snomed=[]; umls=[]

    with gzip.open(inp, 'rt', encoding='utf-8', errors='ignore') as f:
        for line in f:
            try:
                o = json.loads(line)
            except Exception:
                continue
            ids.append(o.get('id'))
            L=o.get('l',{}); D=o.get('d',{}); E=o.get('ext',{})
            le.append(L.get('en','')); lj.append(L.get('ja',''))
            de.append(D.get('en','')); dj.append(D.get('ja',''))
            p31.append(o.get('P31',[]) or [])
            p279.append(o.get('P279',[]) or [])
            mesh.append(E.get('mesh',[]) or [])
            icd10.append(E.get('icd10',[]) or [])
            icd9.append(E.get('icd9',[]) or [])
            snomed.append(E.get('snomed',[]) or [])
            umls.append(E.get('umls',[]) or [])

    df = pd.DataFrame({
        'id': ids,
        'label_en': le,
        'label_ja': lj,
        'desc_en': de,
        'desc_ja': dj,
        'P31': p31,
        'P279': p279,
        'mesh': mesh,
        'icd10': icd10,
        'icd9': icd9,
        'snomed': snomed,
        'umls': umls,
    })

    df.to_parquet(out, index=False)
    print(f"Saved Parquet: {out}")

if __name__ == '__main__':
    main()
