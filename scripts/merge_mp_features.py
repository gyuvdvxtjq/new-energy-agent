#!/usr/bin/env python3
"""Query MP for explicitly documented undoped NCM formula candidates and join results.

Rows with an unknown dopant are skipped; no dopant identity is guessed.
"""
from __future__ import annotations
import argparse,json,os,urllib.parse,urllib.request,math
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parents[1]
def load_env():
 p=ROOT/'.env'
 if p.exists():
  for line in p.read_text().splitlines():
   if '=' in line and not line.lstrip().startswith('#'):
    k,v=line.split('=',1); os.environ.setdefault(k.strip(),v.strip().strip("\"'"))
def fmt(x):
 return f'{float(x):.4g}'.replace('.0','')
def main():
 p=argparse.ArgumentParser(); p.add_argument('--input',type=Path,default=Path('datasets/raw/NMC_numerical_new.csv')); p.add_argument('--out',type=Path,required=True); a=p.parse_args(); load_env()
 if not os.environ.get('MP_API_KEY'): raise SystemExit('MP_API_KEY not configured in project .env')
 df=pd.read_csv(a.input); rows=[]
 params=urllib.parse.urlencode({'chemsys':'Li-Ni-Co-Mn-O','_fields':'material_id,formula_pretty,composition,band_gap,formation_energy_per_atom,energy_above_hull','_limit':'1000'})
 req=urllib.request.Request('https://api.materialsproject.org/materials/summary/?'+params,headers={'X-API-KEY':os.environ['MP_API_KEY'],'User-Agent':'new-energy-agent/0.1'})
 with urllib.request.urlopen(req,timeout=60) as r: candidates=json.load(r).get('data',[])
 def norm(comp):
  total=sum(float(v) for v in comp.values()); return {k:float(comp.get(k,0))/total for k in ('Li','Ni','Co','Mn','O')}
 def target(row):
  return norm({'Li':row.Li,'Ni':row.Ni,'Co':row.Co,'Mn':row.Mn,'O':2.0})
 def distance(x,y): return math.sqrt(sum((x[k]-y[k])**2 for k in ('Li','Ni','Co','Mn','O')))
 for i,row in df.iterrows():
  if float(row.get('M',0) or 0)!=0: continue
  formula=f"Li{fmt(row.Li)}Ni{fmt(row.Ni)}Co{fmt(row.Co)}Mn{fmt(row.Mn)}O2"
  if candidates:
   best=min(candidates,key=lambda item:distance(target(row),norm(item.get('composition',{}))))
   rows.append({'source_row':int(i),'formula_assumption':formula,'mp_material_id':best.get('material_id'),'mp_formula':best.get('formula_pretty'),'mp_band_gap':best.get('band_gap'),'mp_formation_energy_per_atom':best.get('formation_energy_per_atom'),'mp_energy_above_hull':best.get('energy_above_hull'),'composition_distance':distance(target(row),norm(best.get('composition',{}))),'mapping_status':'nearest_chemsys_candidate_requires_review'})
 result=pd.DataFrame(rows); a.out.parent.mkdir(parents=True,exist_ok=True); result.to_csv(a.out,index=False)
 manifest={'input':str(a.input),'output':str(a.out),'queried_rows':int((df['M'].fillna(0)==0).sum()),'matched_rows':len(result),'mp_candidate_count':len(candidates),'mapping_rule':'only M==0; oxygen fixed at O2; nearest candidate within Li-Ni-Co-Mn-O chemical system; unknown dopants skipped','mapping_status':'approximate_requires_human_review','evidence_status':'database_native'}
 a.out.with_suffix('.manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(manifest,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
