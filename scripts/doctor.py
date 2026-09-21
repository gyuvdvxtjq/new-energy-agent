#!/usr/bin/env python3
"""Check the local project layout without requiring third-party packages."""

from pathlib import Path
import sys
import importlib.util


ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    "AGENTS.md",
    "PROJECT_SPEC.md",
    "ARCHITECTURE.md",
    "DECISIONS.md",
    "REQUIREMENTS.md",
    "TASKS.md",
    "commands/research.md",
    "commands/experiment.md",
    "commands/predict.md",
    "commands/review.md",
    "commands/compute.md",
]


def main() -> int:
    missing = [path for path in REQUIRED if not (ROOT / path).exists()]
    if missing:
        print("missing:")
        print("\n".join(f"- {item}" for item in missing))
        return 1
    print(f"project: {ROOT}")
    print(f"required_files: {len(REQUIRED)}")
    for module in ("numpy", "pandas", "sklearn", "pymatgen", "mp_api"):
        status = "available" if importlib.util.find_spec(module) else "optional-missing"
        print(f"python.{module}: {status}")
    print(f"project.env: {'present' if (ROOT / '.env').exists() else 'absent'}")
    print("status: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
