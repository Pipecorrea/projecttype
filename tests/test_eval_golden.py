"""Tests PT-10: golden-set + gate CI."""

from __future__ import annotations

import subprocess
import sys
import unittest

from sni_commons.eval import cargar_golden

from projecttype.golden_eval import evaluar_golden_cascada, gate_golden, load_umbrales
from projecttype.paths import DEFAULT_GOLDEN, DEFAULT_UMBRALES, PROJECT_ROOT
from projecttype.scorer import ScorerConfig


class TestEvalGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = cargar_golden(DEFAULT_GOLDEN)
        cls.umbrales = load_umbrales(DEFAULT_UMBRALES)

    def test_eval_ci_gate_green(self) -> None:
        resultado, _ = evaluar_golden_cascada(
            self.golden,
            enable_l3=True,
            l3_mock=True,
        )
        ok, mensaje = gate_golden(resultado, self.umbrales)
        self.assertTrue(ok, mensaje)
        self.assertGreaterEqual(resultado.metricas["precision_l1_l2"], 0.798)
        self.assertGreaterEqual(resultado.metricas["cobertura_l1_l2"], 0.656)

    def test_l1_degradation_fails_gate(self) -> None:
        degraded = ScorerConfig(min_score=999.0, min_margin=999.0)
        resultado, _ = evaluar_golden_cascada(
            self.golden,
            enable_l3=False,
            l3_mock=True,
            l1_config=degraded,
        )
        ok, _ = gate_golden(resultado, self.umbrales)
        self.assertFalse(ok)
        self.assertLess(resultado.metricas["cobertura_l1_l2"], 0.656)

    def test_eval_golden_script_ci_exit_code(self) -> None:
        proc = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "eval_golden.py"),
                "--ci",
                "--golden",
                str(DEFAULT_GOLDEN),
                "--umbrales",
                str(DEFAULT_UMBRALES),
            ],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)


if __name__ == "__main__":
    unittest.main()
