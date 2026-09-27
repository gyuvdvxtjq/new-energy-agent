"""ABACUS integration: plan (input generation) → (gated) SSH execution → parse.

Red lines enforced HERE, not in prompts:
  * remote execution happens ONLY on the user-provided SSH machine
    (core/sshrun.py, credentials from the environment), inside the fixed
    namespace ~/neagent/<task_id>/ — the runtime never touches paths outside
    its own namespace on that machine
  * execution is only reachable through the tool gateway with the approval
    gate satisfied (dft.plan binds the approval to the exact input content)
  * there is no cloud-job API surface: no submit/status/fetch of remote
    platform jobs, no project ids, no billing credentials in code
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path
from typing import Any

from ..profiles import MaterialProfile


class AbacusError(RuntimeError):
    pass


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
        raise AbacusError(f"STRU has no ATOMIC_POSITIONS entries: {stru_path}")

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
        raise AbacusError(f"profile '{profile.name}' has no structure file")

    n_atoms = count_atoms(profile.structure)
    if n_atoms > profile.max_atoms:
        raise AbacusError(
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
            raise AbacusError(f"orbital path escapes source dir: {rel}")
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

    return {
        "dir": str(out_dir),
        "atoms": n_atoms,
        "engine": profile.engine,
        "basis": tpl["basis_type"],
        "files": copied,
        "notes": profile.notes,
    }


# --------------------------------------------------------------------------
# execution: upload → run on the user's SSH machine → fetch results
# --------------------------------------------------------------------------
def remote_dir(task_id: str) -> str:
    """Fixed remote namespace: ~/neagent/<task_id>. task_id is validated so
    it can never smuggle shell syntax into a remote command line."""
    if not re.fullmatch(r"[A-Za-z0-9._-]+", task_id) or set(task_id) <= {"."}:
        raise AbacusError(
            f"task_id must match [A-Za-z0-9._-]+ and not be all dots "
            f"(got {task_id!r}) — it is used as a remote path segment and "
            "must not carry shell syntax or traversal"
        )
    return f"~/neagent/{task_id}"


def _validate_np(np_mpi: Any) -> int:
    """np_mpi lands on a remote shell command line. CLI dispatch passes every
    kwarg as a string, so without this check np_mpi='2; cmd' would be remote
    command injection. Coerce to a bounded int before any interpolation."""
    try:
        n = int(np_mpi)
    except (TypeError, ValueError):
        raise AbacusError(f"np_mpi must be an integer, got {np_mpi!r}")
    if not 1 <= n <= 128:
        raise AbacusError(f"np_mpi out of range (1..128): {n}")
    return n


def ssh_execute(indir: Path, task_id: str, out_dir: Path, *,
                np_mpi: int = 2, timeout: int = 1800) -> dict[str, Any]:
    """Run the planned calculation on the user's SSH machine.

    Sequence: preflight (mkdir + abacus/mpirun present) → pack ALL inputs
    (orbital directories included) into one tarball → upload → blocking SCF
    run → tar the outputs → download + unpack locally.
    On SCF failure the log is still fetched (it is the evidence of what
    happened); `ok` reflects the remote exit code.
    """
    import tarfile

    from . import sshrun
    np_mpi = _validate_np(np_mpi)  # before ANY command interpolation
    indir, out_dir = Path(indir), Path(out_dir)
    inputs = sorted(f for f in indir.rglob("*") if f.is_file())
    if not inputs:
        raise AbacusError(f"no input files under {indir}; run dft.plan first")
    remote = remote_dir(task_id)
    out_dir.mkdir(parents=True, exist_ok=True)

    r = sshrun.run(f"mkdir -p {remote} && command -v abacus >/dev/null "
                   f"&& command -v mpirun >/dev/null")
    if not r["ok"]:
        return {"ok": False, "stage": "preflight",
                "stdout": r["stdout"][-2000:], "stderr": (
                    "remote preflight failed: need ~/neagent writable and "
                    "'abacus' + 'mpirun' on PATH — " + r["stderr"][-500:])}

    # one archive covers everything write_inputs produced, including orbital
    # directories (a per-file upload loop would silently skip them)
    pkg = out_dir / "inputs.tar.gz"
    with tarfile.open(pkg, "w:gz") as tar:
        tar.add(indir, arcname=".")
    r = sshrun.upload(pkg, f"{remote}/inputs.tar.gz")
    pkg.unlink(missing_ok=True)
    if not r["ok"]:
        return {"ok": False, "stage": "upload",
                "stdout": r["stdout"][-500:], "stderr": r["stderr"][-1000:]}

    # run SCF; even on failure, tar the outputs so the log comes home
    run_cmd = (f"cd {remote} && tar xzf inputs.tar.gz && "
               f"rm -rf OUT.ABACUS log results.tar.gz && "
               f"(OMP_NUM_THREADS=1 mpirun -np {np_mpi} abacus > log 2>&1); "
               f"code=$?; tar czf results.tar.gz OUT.ABACUS log 2>/dev/null; "
               f"exit $code")
    r = sshrun.run(run_cmd, timeout=timeout)

    d = sshrun.download(f"{remote}/results.tar.gz", out_dir / "results.tar.gz")
    if d["ok"]:
        shutil.unpack_archive(out_dir / "results.tar.gz", out_dir, "gztar")
    else:
        return {"ok": False, "stage": "download",
                "stdout": r["stdout"][-1000:], "stderr": d["stderr"][-1000:]}

    return {"ok": r["ok"], "stage": "run", "dir": str(out_dir),
            "log": str(out_dir / "log"),
            "stdout": r["stdout"][-2000:], "stderr": r["stderr"][-1000:]}


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
