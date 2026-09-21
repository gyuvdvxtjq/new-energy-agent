#!/usr/bin/env python3
"""Optional Materials Project query adapter."""
from __future__ import annotations
import argparse, json, os, urllib.parse, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def load_project_env() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key, value = key.strip(), value.strip().strip("\"'")
        if key and key not in os.environ:
            os.environ[key] = value
def main() -> int:
    load_project_env()
    p=argparse.ArgumentParser(); p.add_argument('--formula'); p.add_argument('--material-id'); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    if not os.environ.get('MP_API_KEY'): raise SystemExit('MP_API_KEY is not set. Set it in your shell; it is never written to this project.')
    if not a.formula and not a.material_id: raise SystemExit('provide --formula or --material-id')
    fields='material_id,formula_pretty,band_gap,formation_energy_per_atom,energy_above_hull,structure'
    params={'_fields':fields}
    if a.material_id: params['material_ids']=a.material_id
    if a.formula: params['formula']=a.formula
    url='https://api.materialsproject.org/materials/summary/?'+urllib.parse.urlencode(params)
    request=urllib.request.Request(url,headers={'X-API-KEY':os.environ['MP_API_KEY'],'User-Agent':'new-energy-agent/0.1'})
    try:
        with urllib.request.urlopen(request,timeout=60) as response: payload=json.load(response)
    except Exception as error:
        raise SystemExit(f'Materials Project request failed: {error}')
    result={'source':'Materials Project','query':{'formula':a.formula,'material_id':a.material_id},'endpoint':url.split('?')[0],'evidence_status':'database_native','records':payload.get('data',[]),'meta':payload.get('meta',{})}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2,default=str)+'\n',encoding='utf-8'); print(f"wrote {len(result['records'])} records to {a.out}"); return 0
if __name__=='__main__': raise SystemExit(main())
