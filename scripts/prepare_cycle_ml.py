#!/usr/bin/env python3
"""Prepare a compact, provenance-preserving ML table from a cycler CSV."""
from __future__ import annotations
import argparse
from pathlib import Path
import pandas as pd

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('csv',type=Path); p.add_argument('--header-line',type=int,default=14); p.add_argument('--out',type=Path,required=True); a=p.parse_args()
    df=pd.read_csv(a.csv,skiprows=a.header_line-1)
    needed=['Cycle C','Step Time [s]','Capacity [Ah]','Current [A]','Voltage [V]','Temperature Cell [degC]']
    missing=[x for x in needed if x not in df.columns]
    if missing: raise SystemExit('missing columns: '+', '.join(missing))
    for c in needed: df[c]=pd.to_numeric(df[c],errors='coerce')
    out=pd.DataFrame({'cycle':df['Cycle C'],'step_time_s':df['Step Time [s]'],'capacity_ah':df['Capacity [Ah]'],'current_abs_a':df['Current [A]'].abs(),'voltage_v':df['Voltage [V]'],'temperature_c':df['Temperature Cell [degC]'],'source_group':'zenodo-4032561-cell03'})
    out=out.dropna().reset_index(drop=True)
    a.out.parent.mkdir(parents=True,exist_ok=True); out.to_csv(a.out,index=False); print(f'wrote {len(out)} rows to {a.out}'); return 0
if __name__=='__main__': raise SystemExit(main())
