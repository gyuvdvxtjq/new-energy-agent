"""Evidence chain: manifest with SHA256 of inputs/outputs + cross-validation report.

This is the auditability layer — the differentiator. Every artifact a run
consumes or produces is hashed and pinned with an evidence level.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def manifest(task_id: str, inputs: list[Path], outputs: list[Path],
             meta: dict[str, Any]) -> dict[str, Any]:
    def _entries(paths: list[Path]) -> list[dict[str, str]]:
        return [{"path": str(p), "sha256": sha256(p)} for p in paths if Path(p).exists()]

    return {
        "task_id": task_id,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "inputs": _entries(inputs),
        "outputs": _entries(outputs),
        "meta": meta,
    }


def write_manifest(task_id: str, evidence_dir: Path, inputs: list[Path],
                   outputs: list[Path], meta: dict[str, Any]) -> Path:
    evidence_dir.mkdir(parents=True, exist_ok=True)
    doc = manifest(task_id, inputs, outputs, meta)
    p = evidence_dir / f"{task_id}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


def compare_report(computed: dict[str, Any], database_json: Path) -> dict[str, Any]:
    """Side-by-side `computed` vs `database_native` — the cross-validation story.

    Honest by construction: when the two sides do not share the same calculator
    / functional / pseudopotential, the mismatch is reported as EXPECTED, and a
    same-calculator comparison is listed as follow-up, never fudged.
    """
    db = json.loads(Path(database_json).read_text(encoding="utf-8"))
    # summary endpoints return records[]; a single flat record also works
    rec = (db.get("records") or [{}])[0]
    return {
        "computed": {
            "evidence_level": computed.get("evidence_level", "unverified"),
            "converged": computed.get("converged"),
            "final_etot_ev": computed.get("final_etot_ev"),
            "source": computed.get("log", "abacus run"),
        },
        "database_native": {
            "evidence_level": "database_native",
            "source_id": rec.get("material_id") or rec.get("id") or db.get("material_id"),
            "formula": rec.get("formula_pretty"),
            "band_gap_ev": rec.get("band_gap") or db.get("band_gap"),
            "source": "Materials Project (PBE)",
        },
        "comparable": False,
        "why": (
            "ABACUS total energy (this run) and MP entries use different "
            "calculators/functional/pseudopotentials; direct energy equality is "
            "NOT expected. Same-calculator comparison needs the MP total energy "
            "via MP_API_KEY (roadmap) or a matching MP-compatible calculation."
        ),
        "next_checks": [
            "compare formation energy against MP with the same functional",
            "converge ecutwfc/k-points until total energy changes < 1 meV/atom",
        ],
    }
