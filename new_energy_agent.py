#!/usr/bin/env python3
"""Local command entry point for the New Energy Research Agent toolkit."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def run_script(name: str, args: list[str]) -> int:
    return subprocess.run([sys.executable, str(ROOT / "scripts" / name), *args], cwd=ROOT).returncode

def main() -> int:
    parser = argparse.ArgumentParser(prog="new-energy-agent")
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("init", help="initialize a research task workspace"); p.add_argument("title"); p.add_argument("--task-id")
    p = sub.add_parser("quality", help="run CSV quality and leakage preflight"); p.add_argument("csv"); p.add_argument("--target"); p.add_argument("--group", action="append", default=[]); p.add_argument("--out", required=True)
    p = sub.add_parser("predict", help="run grouped Random Forest baseline"); p.add_argument("--csv"); p.add_argument("--target", default="retention_pct"); p.add_argument("--group"); p.add_argument("--out", required=True); p.add_argument("--demo", action="store_true")
    p = sub.add_parser("compute-plan", help="write a reviewable remote calculation plan"); p.add_argument("goal"); p.add_argument("--structure", required=True); p.add_argument("--method", default="未指定"); p.add_argument("--host", default="未指定"); p.add_argument("--out", required=True)
    p = sub.add_parser("parse-dft", help="parse scalar signals from an OUTCAR-like file"); p.add_argument("path"); p.add_argument("--out", required=True)
    p = sub.add_parser("doctor", help="check project capabilities")
    p = sub.add_parser("self-test", help="run no-network acceptance tests")
    p = sub.add_parser("evaluate", help="score workflow readiness and evidence coverage"); p.add_argument("--root", default="."); p.add_argument("--out", required=True)
    a = parser.parse_args()
    if a.command == "init": return run_script("init_workspace.py", [a.title] + (["--task-id", a.task_id] if a.task_id else []))
    if a.command == "quality": return run_script("data_quality.py", [a.csv, "--out", a.out] + (["--target", a.target] if a.target else []) + sum((["--group", g] for g in a.group), []))
    if a.command == "predict": return run_script("baseline_predict.py", ["--target", a.target, "--out", a.out] + (["--csv", a.csv] if a.csv else []) + (["--group", a.group] if a.group else []) + (["--demo"] if a.demo else []))
    if a.command == "compute-plan": return run_script("compute_plan.py", [a.goal, "--structure", a.structure, "--method", a.method, "--host", a.host, "--out", a.out])
    if a.command == "parse-dft": return run_script("parse_dft_output.py", [a.path, "--out", a.out])
    if a.command == "doctor": return run_script("doctor.py", [])
    if a.command == "evaluate": return run_script("evaluate_run.py", ["--root", a.root, "--out", a.out])
    return run_script("self_test.py", [])

if __name__ == "__main__": raise SystemExit(main())
