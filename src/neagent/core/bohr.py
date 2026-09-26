"""Bohrium integration: plan → dry-run → (gated) submit → status → fetch → parse.

Red lines enforced HERE, not in prompts:
  * every WRITE operation against a Bohrium job requires that job_id to be in
    the task's `job_ids` whitelist (jobs created BY this project) — the runtime
    refuses to touch anything else. Node operations do not exist in this module.
  * real submission is only reachable through the tool gateway with the
    approval gate satisfied; dry-run is always allowed.
  * BOHRIUM_PROJECT_ID comes from the environment (.env), never hardcoded.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any

from ..profiles import MaterialProfile

IMAGE_ABACUS = "registry.dp.tech/dptech/abacus:3.1.0"


class BohrError(RuntimeError):
    pass


# --------------------------------------------------------------------------
# machine routing: agent's resource decision, recorded in the approval file
# --------------------------------------------------------------------------
def route_machine(n_atoms: int, kind: str = "dft") -> str:
    """DFT is CPU-bound (MPI); MLIP inference would be GPU-bound (roadmap)."""
    if kind != "dft":
        raise ValueError(f"unsupported compute kind '{kind}' (mlip is roadmap)")
    if n_atoms <= 20:
        return "c2_m8_cpu"      # ¥0.16/h — Si primitive cell territory
    if n_atoms <= 60:
        return "c8_m32_cpu"
    return "c16_m64_cpu"


def estimate_cost(machine_type: str, minutes: float) -> str:
    rates = {"c2_m8_cpu": 0.16, "c8_m32_cpu": 0.4, "c16_m64_cpu": 0.96}
    rate = rates.get(machine_type, 0.16)
    return f"{machine_type} ¥{rate}/h × {minutes:.0f}min ≈ ¥{rate * minutes / 60:.3f}"


# --------------------------------------------------------------------------
# plan: generate real ABACUS inputs from a profile + parameter template
# --------------------------------------------------------------------------
_SECTION_HEADERS = {"ATOMIC_SPECIES", "NUMERICAL_ORBITAL", "NUMERICAL_DESCRIPTOR",
                    "LATTICE_CONSTANT", "LATTICE_VECTORS", "ATOMIC_POSITIONS"}


def _stru_section(stru_path: Path, section: str) -> list[str]:
    """Return non-comment lines of one STRU section (ends at blank line)."""
    out, inside = [], False
    for raw in stru_path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#")[0].strip()
        if not line:
            if inside:
                break
            continue
        head = line.split()[0].upper()
        if head in _SECTION_HEADERS:
            inside = head == section.upper()
            continue
        if inside:
            out.append(line)
    return out


def count_atoms(stru_path: Path) -> int:
    """Count atoms in an ABACUS STRU ATOMIC_POSITIONS section.

    Handles both ABACUS layouts:
      PW style:   element line, then one coordinate line per atom
      LCAO style: element line, magnetic line, <count> line, then <count> coords
    """
    body = _stru_section(stru_path, "ATOMIC_POSITIONS")
    if not body:
        raise BohrError(f"STRU has no ATOMIC_POSITIONS entries: {stru_path}")

    def is_num(tok: str) -> bool:
        try:
            float(tok)
            return True
        except ValueError:
            return False

    i, total = 0, 0
    if body[i].split()[0].lower() in {"cartesian", "direct"}:
        i += 1
    while i < len(body):
        tok = body[i].split()
        if not tok:
            i += 1
        elif len(tok) == 1:                     # element header
            i += 1
            singles = []
            while i < len(body) and len(body[i].split()) == 1 \
                    and is_num(body[i].split()[0]):
                singles.append(float(body[i].split()[0]))
                i += 1
            if len(singles) >= 2:               # LCAO: magnetic + atom count
                n = int(singles[1])
                total += n
                i += n                          # skip the n coordinate lines
        elif len(tok) >= 3 and all(is_num(t) for t in tok[:3]):
            total += 1                          # PW-style coordinate line
            i += 1
        else:
            i += 1
    return total


def _referenced_files(stru_path: Path) -> tuple[list[str], list[str]]:
    """Pseudopotential files (ATOMIC_SPECIES col 3) and orbital entries."""
    pseudo = []
    for line in _stru_section(stru_path, "ATOMIC_SPECIES"):
        parts = line.split()
        if len(parts) >= 3:
            pseudo.append(parts[2])
    orbitals = [line.split()[0]
                for line in _stru_section(stru_path, "NUMERICAL_ORBITAL")]
    return pseudo, orbitals


def write_inputs(profile: MaterialProfile, out_dir: Path) -> dict[str, Any]:
    """Materialize INPUT/STRU/KPT/pseudo/orbital files under out_dir."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not profile.structure:
        raise BohrError(f"profile '{profile.name}' has no structure file")

    n_atoms = count_atoms(profile.structure)
    if n_atoms > profile.max_atoms:
        raise BohrError(
            f"plan refused: {n_atoms} atoms exceeds profile budget "
            f"max_atoms={profile.max_atoms} — shrink the cell or raise the budget "
            "explicitly (that is a user decision, not an agent decision)"
        )

    src_dir = profile.structure.parent
    copied = []
    pseudo, orbitals = _referenced_files(profile.structure)
    for name in [profile.structure.name, *pseudo,
                 *profile.load_template().get("pseudo_files", [])]:
        src = src_dir / name
        if not src.exists():
            raise FileNotFoundError(f"missing input file for plan: {src}")
        if name not in copied:
            (out_dir / name).write_bytes(src.read_bytes())
            copied.append(name)

    # orbital entries: files OR directories, referenced as ./<name> in STRU —
    # copy under the same basename so the reference stays valid
    for rel in orbitals:
        src = (src_dir / rel).resolve()
        if not src.is_relative_to(src_dir.resolve()):
            raise BohrError(f"orbital path escapes source dir: {rel}")
        dest = out_dir / Path(rel).name
        if src.is_dir():
            shutil.copytree(src, dest, dirs_exist_ok=True)
            copied.append(Path(rel).name + "/")
        else:
            dest.write_bytes(src.read_bytes())
            copied.append(Path(rel).name)

    kpt_src = src_dir / "KPT"
    if kpt_src.exists():
        (out_dir / "KPT").write_bytes(kpt_src.read_bytes())
        copied.append("KPT")
    else:
        (out_dir / "KPT").write_text(
            "KPOINTS\n0\nGamma\n1 1 1 0 0 0\n", encoding="utf-8")
        copied.append("KPT(generated)")

    tpl = profile.load_template()
    input_text = (
        "INPUT_PARAMETERS\n"
        f"ntype\t\t\t{tpl['ntype']}\n"
        f"ecutwfc\t\t\t{tpl['ecutwfc']}\n"
        f"scf_nmax\t\t{tpl['scf_nmax']}\n"
        f"scf_thr\t\t\t{tpl['scf_thr']:g}\n"
        f"basis_type\t\t{tpl['basis_type']}\n"
        f"symmetry\t\t{tpl.get('symmetry', 0)}\n"
    )
    (out_dir / "INPUT").write_text(input_text, encoding="utf-8")

    machine = route_machine(n_atoms)
    return {
        "dir": str(out_dir),
        "atoms": n_atoms,
        "engine": profile.engine,
        "basis": tpl["basis_type"],
        "files": copied,
        "machine_type": machine,
        "estimated_cost": estimate_cost(machine, minutes=2),
        "notes": profile.notes,
    }


def build_job_json(out_dir: Path, job_name: str, machine_type: str,
                   np_mpi: int = 2) -> Path:
    project_id = os.environ.get("BOHRIUM_PROJECT_ID")
    if not project_id:
        raise BohrError(
            "BOHRIUM_PROJECT_ID is not set — put it in .env and export it. "
            "Dry-run works without it; real submission does not."
        )
    job = {
        "job_name": job_name,
        "command": f"OMP_NUM_THREADS=1 mpirun -np {np_mpi} abacus > log",
        "log_file": "log",
        "backward_files": ["OUT.ABACUS"],
        "project_id": int(project_id),
        "platform": "ali",
        "job_type": "container",
        "machine_type": machine_type,
        "image_address": IMAGE_ABACUS,
    }
    p = Path(out_dir) / "job.json"
    p.write_text(json.dumps(job, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return p


# --------------------------------------------------------------------------
# execution: dry-run always allowed; real submit is the gated path
# --------------------------------------------------------------------------
def _run_bohr(args: list[str], timeout: int = 120) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            ["bohr", *args], capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        raise BohrError("bohr CLI not found on PATH (install via pip install bohrium)")


def dry_run(job_json: Path) -> dict[str, Any]:
    """Validate job.json via the CLI's own dry-run. No cost, no state change."""
    r = _run_bohr(["job", "submit", "--dry-run", "--file", str(job_json)])
    return {
        "ok": r.returncode == 0,
        "stdout": r.stdout[-2000:],
        "stderr": r.stderr[-2000:],
        "mode": "dry-run (no cost, nothing submitted)",
    }


def submit(job_json: Path) -> dict[str, Any]:
    """Real submission. Reachable ONLY through the tool gateway with the
    approval gate satisfied; the caller (tools.py) registers the returned
    job_id into the task whitelist after success."""
    r = _run_bohr(["job", "submit", "--file", str(job_json)], timeout=300)
    out = r.stdout + "\n" + r.stderr
    m = re.search(r"[Jj]ob[_ ]?[Ii]d[:\s=]+(\d+)", out)
    return {
        "ok": r.returncode == 0,
        "job_id": m.group(1) if m else None,
        "stdout": r.stdout[-2000:],
        "stderr": r.stderr[-2000:],
    }


def job_status(job_id: str) -> dict[str, Any]:
    r = _run_bohr(["job", "info", "--job-id", str(job_id)])
    return {"ok": r.returncode == 0, "stdout": r.stdout[-2000:], "stderr": r.stderr[-1000:]}


def fetch(job_id: str, out_dir: Path, *, owns_job: Any) -> dict[str, Any]:
    """Download results. Red line: refuse any job_id not owned by this task."""
    if not owns_job(job_id):
        raise BohrError(
            f"refused: job {job_id} is not in this task's job_ids whitelist. "
            "The runtime only touches resources this project created."
        )
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    r = _run_bohr(["job", "download", "--job-id", str(job_id), "--source",
                   str(out_dir)], timeout=600)
    return {"ok": r.returncode == 0, "dir": str(out_dir),
            "stdout": r.stdout[-2000:], "stderr": r.stderr[-1000:]}


# --------------------------------------------------------------------------
# parse: evidence extraction from ABACUS output
# --------------------------------------------------------------------------
def parse_output(log_text: str, *, converged_marker: str | list[str] = "convergence has been achieved",
                 energy_pattern: str = "final etot is") -> dict[str, Any]:
    markers = [converged_marker] if isinstance(converged_marker, str) else converged_marker
    converged = any(m in log_text for m in markers)
    energies = [
        float(line.split(energy_pattern)[1].split()[0])
        for line in log_text.splitlines()
        if energy_pattern in line
    ]
    # ABACUS writes a high-precision summary line at the end when it converges
    m = re.search(r"!FINAL_ETOT_IS\s+(-?[\d.]+)\s*eV", log_text)
    final = float(m.group(1)) if m else (energies[-1] if energies else None)
    return {
        "converged": converged,
        "final_etot_ev": final,
        "scf_steps": len(energies),
        "evidence_level": "computed" if converged and final is not None else "unverified",
        "limits": (
            "total energy depends on pseudopotential/functional/basis; only "
            "same-calculator comparisons are meaningful (e.g. ABACUS-LDA vs MP-PBE "
            "is an EXPECTED mismatch, not an error)"
        ),
    }


def parse_log_file(log_path: Path, template_output: dict | None = None) -> dict[str, Any]:
    t = template_output or {}
    result = parse_output(
        Path(log_path).read_text(encoding="utf-8", errors="replace"),
        converged_marker=t.get("converged_marker", "convergence has been achieved"),
        energy_pattern=t.get("energy_pattern", "final etot is"),
    )
    result["log"] = str(log_path)
    return result
