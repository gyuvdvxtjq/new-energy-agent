"""Material profiles — pluggable per-material-system configuration.

换材料体系 = 加一个 profiles/<name>.yaml，零代码改动：
  * material.structure  本地结构文件（或 roadmap: MP ID）
  * material.source     预测链数据 CSV（无则预测链不适用）
  * compute.template    ABACUS 参数模板（profiles/templates/*.yaml）
  * budget.max_atoms    计算预算（超限由 dft.plan 直接拒单——预算是用户决定）
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .paths import repo_root

PROFILES_DIR = "profiles"


@dataclass
class MaterialProfile:
    name: str
    display_name: str
    source: Path | None
    structure: Path | None
    mp_id: str | None
    engine: str
    template: Path | None
    max_atoms: int
    estimated_cost_note: str
    prediction_target: str | None
    prediction_group: str | None
    notes: str

    def load_template(self) -> dict[str, Any]:
        if not self.template:
            return {}
        return yaml.safe_load(self.template.read_text(encoding="utf-8"))


def _repo_path(v: str | None) -> Path | None:
    return (repo_root() / v).resolve() if v else None


def load_profile(name: str, profiles_dir: Path | None = None) -> MaterialProfile:
    base = Path(profiles_dir) if profiles_dir else repo_root() / PROFILES_DIR
    p = base / f"{name}.yaml"
    if not p.exists():
        raise FileNotFoundError(f"unknown profile '{name}': {p} not found")
    raw = yaml.safe_load(p.read_text(encoding="utf-8"))
    material, compute = raw.get("material", {}), raw.get("compute", {})
    budget, prediction = raw.get("budget", {}), raw.get("prediction", {}) or {}
    structure = _repo_path(material.get("structure"))
    # a compute-capable profile needs a structure (local file, or MP id later);
    # predict-only profiles (CSV source, no template) are fine without one
    if compute.get("template") and not structure and material.get("mp_id") is None:
        raise ValueError(f"profile '{name}': compute.template set but no "
                         "material.structure or material.mp_id")
    return MaterialProfile(
        name=name,
        display_name=material.get("name", name),
        source=_repo_path(material.get("source")),
        structure=structure,
        mp_id=material.get("mp_id"),
        engine=compute.get("engine", "abacus"),
        template=_repo_path(compute.get("template")),
        max_atoms=int(budget.get("max_atoms", 120)),
        estimated_cost_note=budget.get("estimated_cost_note", ""),
        prediction_target=prediction.get("target"),
        prediction_group=prediction.get("group"),
        notes=(raw.get("notes") or "").strip(),
    )
