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
    check('material_performance_dataset',10,any((r/'datasets'/'raw').glob('NMC_numerical_new.csv')),'NCM-ML public material dataset')
    mp_join = (r/'reports'/'ncm_mp_features.csv').exists() and (r/'reports'/'ncm_mp_features.manifest.json').exists()
    check('dft_feature_join',10,mp_join,'reports/ncm_mp_features.csv; mapping is approximate and requires human review')
    check('live_remote_compute',5,any((r/'calculations').glob('**/parsed_result.json')),'requires confirmed SSH/Slurm result')
    engineering=round(sum(x['weight'] for x in checks if x['passed'])/sum(x['weight'] for x in checks)*100,1)
    scientific=round(sum(x['weight'] for x in checks if x['passed'] and x['name'] not in {'dft_feature_join','live_remote_compute'})/sum(x['weight'] for x in checks)*100,1)
    result={'engineering_readiness':engineering,'scientific_demo_readiness':scientific,'max_score':100,'checks':checks,'interpretation':'readiness score, not a scientific validity score; missing DFT join and remote compute are explicit failures','limitations':['Does not replace expert review, a real Materials Project query, or external compute validation.']}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n'); print(json.dumps(result,ensure_ascii=False,indent=2)); return 0 if engineering>=80 else 1
if __name__=='__main__': raise SystemExit(main())
