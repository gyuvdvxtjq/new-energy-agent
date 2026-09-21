#!/usr/bin/env python3
"""Quantify a research-agent run using auditable artifact checks."""
from __future__ import annotations
import argparse,json
from pathlib import Path

def main() -> int:
    p=argparse.ArgumentParser(); p.add_argument('--root',type=Path,default=Path('.')); p.add_argument('--out',type=Path,required=True); a=p.parse_args(); r=a.root
    checks=[]
    def check(name,weight,ok,evidence): checks.append({'name':name,'weight':weight,'passed':bool(ok),'evidence':evidence})
    check('project_spec',10,(r/'PROJECT_SPEC.md').exists(),'PROJECT_SPEC.md')
    check('workflow_commands',10,all((r/'commands'/f'{n}.md').exists() for n in ('research','experiment','predict','review','compute')),'commands/*.md')
    check('provenance',15,(r/'datasets'/'SOURCES.md').exists() and any((r/'datasets'/'raw').glob('*.manifest.json')),'datasets/SOURCES.md + raw manifest')
    check('data_quality',15,(r/'scripts'/'data_quality.py').exists(),'scripts/data_quality.py')
    check('leakage_control',15,'group' in (r/'scripts'/'baseline_predict.py').read_text(),'group-aware baseline')
    check('reproducibility',15,(r/'tests'/'test_toolkit.py').exists() and (r/'scripts'/'self_test.py').exists(),'tests + self_test')
    check('compute_approval',10,'waiting_user_approval' in (r/'scripts'/'compute_plan.py').read_text(),'compute plan approval gate')
    check('dft_parser',10,(r/'scripts'/'parse_dft_output.py').exists(),'scripts/parse_dft_output.py')
    score=round(sum(x['weight'] for x in checks if x['passed'])/sum(x['weight'] for x in checks)*100,1)
    result={'score':score,'max_score':100,'checks':checks,'interpretation':'tooling and workflow readiness score; not a scientific validity score','limitations':['Does not replace expert review or external compute validation.']}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if score>=80 else 1
if __name__=='__main__': raise SystemExit(main())
