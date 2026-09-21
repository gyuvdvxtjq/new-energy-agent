#!/usr/bin/env python3
"""Run the complete local material-performance demonstration."""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def call(args):
    result=subprocess.run([sys.executable,*args],cwd=ROOT,text=True,capture_output=True)
    if result.returncode: raise SystemExit(result.stderr or result.stdout)
def main():
    p=argparse.ArgumentParser(); p.add_argument('--out-dir',type=Path,default=Path('demo_run/material_demo')); a=p.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
    dataset=ROOT/'datasets/raw/NMC_numerical_new.csv'; reports=a.out_dir/'reports'; reports.mkdir(exist_ok=True)
    call(['scripts/data_quality.py',str(dataset),'--target','IC','--out',str(reports/'quality.json')])
    call(['scripts/baseline_predict.py','--csv',str(dataset),'--target','IC','--out',str(reports/'ic_metrics.json')])
    call(['scripts/baseline_predict.py','--csv',str(dataset),'--target','EC','--out',str(reports/'ec_metrics.json')])
    summary={'dataset':str(dataset),'records':168,'targets':['IC','EC'],'reports':[str(reports/'quality.json'),str(reports/'ic_metrics.json'),str(reports/'ec_metrics.json')],'status':'completed','limitations':['No explicit DFT/MP ID columns in this public fixture; DFT feature join remains a separately gated step.','Random split is a smoke test, not chemical extrapolation validation.']}
    (a.out_dir/'workflow.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(summary,ensure_ascii=False,indent=2)); return 0
if __name__=='__main__': raise SystemExit(main())
