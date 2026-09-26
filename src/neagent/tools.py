"""Tool registry — binds the deterministic core into the gateway.

Every capability the host LLM can invoke is registered here exactly once, with
its permission attributes and state-machine contract. NOTE: `gate.approve` is
deliberately NOT a gateway tool — approval is a human act (edit the approvals
file or run `neagent gate approve` in a terminal). The agent's tool surface
physically contains no way to approve itself.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .core import bohr, data, evidence, features, models
from .paths import workspace_root
from .profiles import load_profile
from .runtime.gate import ApprovalGate
from .runtime.gateway import ToolGateway, ToolSpec
from .runtime.state import TaskStore


@dataclass
class Runtime:
    store: TaskStore
    gate: ApprovalGate
    gateway: ToolGateway
    root: Path


def build_runtime(workspace: Path | None = None) -> Runtime:
    root = Path(workspace) if workspace else workspace_root()
    store = TaskStore(root)
    gate = ApprovalGate(root)
    gw = ToolGateway(root, store, gate)
    rt = Runtime(store, gate, gw, root)
    _register(rt)
    return rt


# --------------------------------------------------------------------------
# tool implementations (closures over the runtime)
# --------------------------------------------------------------------------
def _register(rt: Runtime) -> None:
    store, gate, gw = rt.store, rt.gate, rt.gateway

    def task_dir(task_id: str) -> Path:
        return rt.root / "tasks" / task_id

    # -- lifecycle -----------------------------------------------------------
    def task_init(task_id: str | None = None, title: str = "untitled",
                  workflow: str = "predict") -> dict:
        if not task_id:
            import time as _t
            task_id = f"task-{_t.strftime('%Y%m%d-%H%M%S')}"
        return store.create(task_id, title, workflow)

    def task_status(task_id: str) -> dict:
        return store.load(task_id)

    def task_list(task_id: str | None = None) -> list[dict]:
        out = []
        for p in sorted((rt.root / "tasks").glob("*/task.yaml")):
            doc = store.load(p.parent.name)
            out.append({"task_id": doc["task_id"], "state": doc["state"],
                        "workflow": doc["workflow"], "title": doc["title"]})
        return out

    def task_resume(task_id: str, note: str = "") -> dict:
        doc = store.load(task_id)
        doc["resume_note"] = note or doc.get("resume_note", "")
        store._write(store.path(task_id), doc)  # persist note before transition
        return {"resumed": task_id, "note": note}

    # -- predict chain -------------------------------------------------------
    def data_quality(task_id: str, csv: str | None = None,
                     profile_name: str | None = None, out: str | None = None) -> dict:
        profile = load_profile(profile_name) if profile_name else None
        csv_path = Path(csv) if csv else (profile.source if profile else None)
        if not csv_path:
            raise ValueError("provide --csv or a profile with material.source")
        report = data.quality_report(csv_path,
                                     target=profile.prediction_target if profile else None,
                                     group=[profile.prediction_group] if profile and profile.prediction_group else None)
        out_path = Path(out) if out else task_dir(task_id) / "outputs" / "quality.json"
        data.write_report(report, out_path)
        return {"report": str(out_path), "rows": report["rows"],
                "warnings": report["warnings"]}

    def features_derive(task_id: str, csv: str | None = None,
                        formula_column: str = "Name",
                        profile_name: str | None = None,
                        out: str | None = None) -> dict:
        import pandas as pd
        profile = load_profile(profile_name) if profile_name else None
        csv_path = Path(csv) if csv else (profile.source if profile else None)
        if not csv_path:
            raise ValueError("provide --csv or a profile with material.source")
        frame = pd.read_csv(csv_path)
        if formula_column in frame.columns:
            feats, failures = features.derive_frame(frame, formula_column)
            frame = pd.concat([frame, feats], axis=1)
            note = None
        else:
            # e.g. NCM datasets ship element amounts as numeric columns already;
            # derivation is a no-op, NOT an error — say so explicitly.
            failures, feats, note = [], None, (
                f"no '{formula_column}' column; dataset appears to carry elemental "
                "amounts directly — feature derivation skipped")
        out_path = Path(out) if out else task_dir(task_id) / "outputs" / "features.csv"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(out_path, index=False)
        return {"features_csv": str(out_path), "note": note, "failures": failures}

    def models_baseline(task_id: str, csv: str | None = None,
                        target: str | None = None, group: str | None = None,
                        profile_name: str | None = None,
                        out: str | None = None) -> dict:
        import pandas as pd
        profile = load_profile(profile_name) if profile_name else None
        csv_path = Path(csv) if csv else (profile.source if profile else None)
        if not csv_path:
            raise ValueError("provide --csv or a profile with material.source")
        target = target or (profile.prediction_target if profile else None)
        group = group or (profile.prediction_group if profile else None)
        if not target:
            raise ValueError("no prediction target (profile or --target)")
        result = models.run(pd.read_csv(csv_path), target, group)
        out_path = Path(out) if out else task_dir(task_id) / "outputs" / "baseline_metrics.json"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n",
                            encoding="utf-8")
        return {"metrics": str(out_path), "split_rule": result["split_rule"],
                "mae": result["metrics"]["mae"], "r2": result["metrics"]["r2"]}

    # -- compute chain -------------------------------------------------------
    def bohr_plan(task_id: str, profile_name: str = "si",
                  out_dir: str | None = None) -> dict:
        profile = load_profile(profile_name)
        indir = Path(out_dir) if out_dir else task_dir(task_id) / "inputs"
        plan = bohr.write_inputs(profile, indir)
        job_json = bohr.build_job_json(indir, job_name=task_id,
                                       machine_type=plan["machine_type"])
        gate.create_request(
            task_id,
            command=f"bohr job submit --file {job_json} (ABACUS SCF, {plan['engine']}/{plan['basis']})",
            inputs=f"{plan['files']} @ {plan['dir']} ({plan['atoms']} atoms, profile={profile_name})",
            estimated_cost=plan["estimated_cost"],
            risks="spends Bohrium quota; remote job on user account; failure recoverable via resubmit",
            failure_policy="on failure: record error, state→failed, resume=planned; never auto-retry paid ops",
        )
        evidence.write_manifest(
            task_id, rt.root / "evidence",
            inputs=[Path(indir) / f for f in plan["files"]] + [job_json],
            outputs=[],
            meta={"stage": "plan", "machine": plan["machine_type"],
                  "estimated_cost": plan["estimated_cost"], "engine": plan["engine"]},
        )
        plan["job_json"] = str(job_json)
        plan["approval_file"] = str(gate.path(task_id))
        return plan

    def bohr_dryrun(task_id: str, job_json: str | None = None) -> dict:
        p = Path(job_json) if job_json else task_dir(task_id) / "inputs" / "job.json"
        return bohr.dry_run(p)

    def bohr_submit(task_id: str, job_json: str | None = None) -> dict:
        p = Path(job_json) if job_json else task_dir(task_id) / "inputs" / "job.json"
        result = bohr.submit(p)
        if result["ok"] and result["job_id"]:
            store.add_job_id(task_id, result["job_id"])
        return result

    def bohr_status(task_id: str, job_id: str | None = None) -> dict:
        jid = job_id or _last_job(store, task_id)
        return bohr.job_status(jid)

    def bohr_fetch(task_id: str, job_id: str | None = None,
                   out_dir: str | None = None) -> dict:
        jid = job_id or _last_job(store, task_id)
        dest = Path(out_dir) if out_dir else task_dir(task_id) / "download"
        return bohr.fetch(jid, dest,
                          owns_job=lambda j, _t=task_id: store.owns_job(_t, j))

    def dft_parse(task_id: str, log_path: str | None = None,
                  profile_name: str | None = None) -> dict:
        profile = load_profile(profile_name) if profile_name else None
        tpl_out = profile.load_template().get("output", {}) if profile else {}
        if not log_path:
            candidates = []
            base = task_dir(task_id)
            for c in tpl_out.get("log_candidates", ["OUT.ABACUS/running_scf.log"]):
                candidates += list(base.rglob(Path(c).name))
            if not candidates:
                raise FileNotFoundError(
                    f"no ABACUS log found under {base}; pass log_path explicitly")
            log_path = str(candidates[0])
        parsed = bohr.parse_log_file(Path(log_path), tpl_out)
        out = task_dir(task_id) / "outputs" / "parsed.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(parsed, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8")
        return parsed

    def evidence_report(task_id: str, database_json: str | None = None) -> dict:
        parsed_p = task_dir(task_id) / "outputs" / "parsed.json"
        if not parsed_p.exists():
            raise FileNotFoundError(f"run dft.parse first: {parsed_p} missing")
        parsed = json.loads(parsed_p.read_text(encoding="utf-8"))
        db = Path(database_json) if database_json else None
        meta: dict[str, Any] = {"stage": "report", "computed": parsed}
        if db and db.exists():
            meta["comparison"] = evidence.compare_report(parsed, db)
        mpath = evidence.write_manifest(
            task_id, rt.root / "evidence",
            inputs=[parsed_p] + ([db] if db else []),
            outputs=[rt.root / "evidence" / f"{task_id}.json"],
            meta=meta,
        )
        return {"manifest": str(mpath), "comparison": meta.get("comparison")}

    # -- registration (permission + state contract per tool) -----------------
    specs = [
        ToolSpec("task.init", task_init, "create a task (draft)",
                 write=True, requires_task=False),
        ToolSpec("task.status", task_status, "load full task doc (state, history, steps, job_ids)",
                 read=True),
        ToolSpec("task.list", task_list, "list all tasks", read=True, requires_task=False),
        ToolSpec("task.resume", task_resume, "resume a failed task (failed→planned)",
                 write=True, allowed_states=["failed"], success_trigger="resume"),
        ToolSpec("data.quality", data_quality, "quality/leakage preflight report",
                 read=True, write=True, allowed_states=["planned", "running"]),
        ToolSpec("features.derive", features_derive, "composition features from formulae",
                 read=True, write=True, allowed_states=["planned", "running"]),
        ToolSpec("models.baseline", models_baseline, "RF baseline with leakage-honest split",
                 write=True, allowed_states=["running"], success_trigger="finish"),
        ToolSpec("bohr.plan", bohr_plan,
                 "generate ABACUS inputs + job.json + approval request (no cost)",
                 write=True, allowed_states=["planned"], success_trigger="request_submit"),
        ToolSpec("bohr.dryrun", bohr_dryrun, "validate job.json via CLI dry-run (no cost)",
                 read=True, network=True, allowed_states=["planned", "waiting_approval", "approved"]),
        ToolSpec("bohr.submit", bohr_submit, "REAL submission — paid, gated",
                 write=True, network=True, paid=True, gated=True,
                 allowed_states=["approved"], success_trigger="execute"),
        ToolSpec("bohr.status", bohr_status, "query job status (whitelist-checked id)",
                 read=True, network=True),
        ToolSpec("bohr.fetch", bohr_fetch, "download job results (whitelist-enforced)",
                 write=True, network=True, allowed_states=["running"],
                 success_trigger="finish"),
        ToolSpec("dft.parse", dft_parse, "extract convergence/energy from ABACUS log",
                 read=True, write=True, allowed_states=["running", "needs_review"]),
        ToolSpec("evidence.report", evidence_report,
                 "SHA256 manifest + computed-vs-database comparison (accept→completed)",
                 write=True, allowed_states=["needs_review"], success_trigger="accept"),
    ]
    for s in specs:
        gw.register(s)

    # state helper tools that only flip state (plan/execute/cancel/reject)
    def _flip(trigger: str, allowed: list[str], desc: str):
        def fn(task_id: str | None = None) -> dict:
            # 'execute' from 'planned' is the local (non-paid) shortcut; the
            # paid path (approved→running) is only reachable via bohr.submit.
            state = store.transition(task_id, trigger,
                                     allow_local_shortcut=(trigger == "execute"))
            return {"task_id": task_id, "state": state.value}
        gw.register(ToolSpec(f"task.{trigger}", fn, desc, write=True,
                             allowed_states=allowed))  # no success_trigger: fn already flipped

    _flip("plan", ["draft"], "draft→planned after scope is clear")
    _flip("execute", ["planned", "approved"],
          "planned→running (local) or approved→running (after gate)")
    _flip("finish", ["running"],
          "running→needs_review once artifacts are fetched and parsed")
    _flip("reject", ["waiting_approval"], "user declined: waiting_approval→planned")
    _flip("cancel", ["draft", "planned", "waiting_approval", "approved",
                     "running", "needs_review", "failed"], "cancel the task")
    # confirm (waiting_approval→approved) is ALSO human-only, like gate.approve.


def _last_job(store: TaskStore, task_id: str) -> str:
    jids = store.load(task_id).get("job_ids", [])
    if not jids:
        raise ValueError(f"task '{task_id}' has no job ids (nothing submitted yet)")
    return jids[-1]
