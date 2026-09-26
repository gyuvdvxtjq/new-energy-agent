"""Regression tests for bohr.plan input generation (first real DFT findings)."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from neagent.core import bohr  # noqa: E402
from neagent.profiles import load_profile  # noqa: E402

FIXTURE = REPO / "tests" / "fixtures" / "abacus_si_example"


class CountAtomsTests(unittest.TestCase):
    def test_lcao_style_counts_two(self):
        # LCAO STRU: element / magnetic / count / coords — the naive parser
        # returned 3 here (it counted the magnetic and count lines as atoms)
        self.assertEqual(bohr.count_atoms(FIXTURE / "STRU"), 2)

    def test_pw_style_counts_each_coord_line(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "STRU"
            p.write_text(
                "ATOMIC_POSITIONS\nCartesian\nSi\n"
                "0.00 0.00 0.00 0 0 0\n0.25 0.25 0.25 1 1 1\n",
                encoding="utf-8")
            self.assertEqual(bohr.count_atoms(p), 2)


class WriteInputsTests(unittest.TestCase):
    def test_copies_orbital_and_pseudo_referenced_by_stru(self):
        profile = load_profile("si")
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "inputs"
            plan = bohr.write_inputs(profile, out)
            names = {p for p in plan["files"]}
            # STRU references ./Si_lda_8.0au_50Ry_2s2p1d and Si.pz-vbc.UPF —
            # the orbital file must be copied or the remote run aborts
            self.assertIn("Si.pz-vbc.UPF", names)
            self.assertIn("Si_lda_8.0au_50Ry_2s2p1d", names)
            self.assertTrue((out / "Si_lda_8.0au_50Ry_2s2p1d").exists())
            self.assertTrue((out / "STRU").exists())
            self.assertTrue((out / "INPUT").exists())
            self.assertTrue((out / "KPT").exists())
            self.assertEqual(plan["atoms"], 2)

    def test_budget_refusal(self):
        profile = load_profile("si")
        object.__setattr__(profile, "max_atoms", 1)  # force-refuse: user decision
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(bohr.BohrError):
                bohr.write_inputs(profile, Path(d) / "inputs")


class ParseOutputTests(unittest.TestCase):
    def test_abacus3_marker_and_precise_energy(self):
        log = ("STEP: 7\n charge density convergence is achieved\n"
               " final etot is -213.6645734 eV\n !FINAL_ETOT_IS -213.6645733985001 eV\n")
        # markers come from the profile template (see abacus_scf_lcao.yaml)
        r = bohr.parse_output(log, converged_marker=[
            "charge density convergence is achieved",   # ABACUS 3.x
            "convergence has been achieved"])           # legacy
        self.assertTrue(r["converged"])
        self.assertEqual(r["evidence_level"], "computed")
        self.assertAlmostEqual(r["final_etot_ev"], -213.6645733985001)

    def test_legacy_marker(self):
        log = "final etot is -7.9 eV\nconvergence has been achieved\n"
        self.assertTrue(bohr.parse_output(log)["converged"])

    def test_unconverged_is_unverified(self):
        r = bohr.parse_output("scf did not finish")
        self.assertFalse(r["converged"])
        self.assertEqual(r["evidence_level"], "unverified")


if __name__ == "__main__":
    unittest.main()
