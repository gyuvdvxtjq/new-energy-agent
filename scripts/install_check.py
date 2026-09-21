#!/usr/bin/env python3
from pathlib import Path
import os
ROOT=Path(__file__).resolve().parents[1]
def main():
    ok=True
    bases=(Path(os.environ.get('CODEX_HOME',str(Path.home()/'.codex')))/'skills',Path.home()/'.claude'/'skills')
    for base in bases:
        for name in ('research','experiment','predict','review','compute'):
            link=base/f'new-energy-{name}'; good=link.is_symlink() and link.resolve()==ROOT/'skills'/name; print(f'{base.name}/{link.name}: {"ok" if good else "missing"}'); ok=ok and good
    return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
