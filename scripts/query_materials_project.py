#!/usr/bin/env python3
"""Optional Materials Project query adapter."""
from __future__ import annotations
import argparse, json, os
from pathlib import Path
def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--formula'); p.add_argument('--material-id'); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    if not os.environ.get('MP_API_KEY'): raise SystemExit('MP_API_KEY is not set. Set it in your shell; it is never written to this project.')
    try:
        from mp_api.client import MPRester
    except ImportError as e: raise SystemExit('mp-api is not installed. Install with: python3 -m pip install mp-api pymatgen') from e
    if not a.formula and not a.material_id: raise SystemExit('provide --formula or --material-id')
    with MPRester() as mpr:
        fields=['material_id','formula_pretty','structure','band_gap','formation_energy_per_atom','energy_above_hull']
        docs=mpr.materials.summary.search(material_ids=[a.material_id],fields=fields) if a.material_id else mpr.materials.summary.search(formula=a.formula,fields=fields)
    result={'source':'Materials Project','query':{'formula':a.formula,'material_id':a.material_id},'evidence_status':'database_native','records':[doc.model_dump(mode='json') if hasattr(doc,'model_dump') else doc.dict() for doc in docs]}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(f'wrote {len(docs)} records to {a.out}'); return 0
if __name__=='__main__': raise SystemExit(main())
