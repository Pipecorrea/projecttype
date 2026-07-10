"""Tests PT-10/PT-17: golden-set expost + gate CI."""

from __future__ import annotations

import subprocess
import sys
import unittest

from sni_commons.eval import cargar_golden

from projecttype.embeddings import L2Config
from projecttype.golden_eval import (
    evaluar_golden_cascada,
    filtrar_casos_por_estrato,
    gate_golden,
    load_umbrales,
    metricas_cascada,
    metricas_l3_puro,
)
from projecttype.paths import (
    DEFAULT_GOLDEN,
    DEFAULT_UMBRALES,
    GOLDEN_FIXTURE,
    PROJECT_ROOT,
)
from projecttype.scorer import ScorerConfig


class TestEvalGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.golden = cargar_golden(DEFAULT_GOLDEN)
        cls.fixture = cargar_golden(GOLDEN_FIXTURE)
        cls.umbrales = load_umbrales(DEFAULT_UMBRALES)

    def test_eval_ci_gate_green(self) -> None:
        resultado, _ = evaluar_golden_cascada(
            self.golden,
            enable_l3=True,
            l3_mock=True,
        )
        ok, mensaje = gate_golden(resultado, self.umbrales)
        self.assertTrue(ok, mensaje)
        self.assertGreaterEqual(
            resultado.metricas["precision_l1_l2"], self.umbrales.precision_l1_l2
        )
        self.assertGreaterEqual(
            resultado.metricas["cobertura_l1_l2"], self.umbrales.cobertura_l1_l2
        )
        self.assertEqual(resultado.metricas["casos_estrato"], 2357.0)

    def test_l1_degradation_fails_gate(self) -> None:
        degraded_l1 = ScorerConfig(min_score=999.0, min_margin=999.0)
        degraded_l2 = L2Config(min_similarity=999.0, min_margin=999.0)
        resultado, _ = evaluar_golden_cascada(
            self.fixture,
            enable_l3=False,
            l3_mock=True,
            l1_config=degraded_l1,
            l2_config=degraded_l2,
            estrato_gate=None,
        )
        ok, _ = gate_golden(resultado, self.umbrales)
        self.assertFalse(ok)
        self.assertLess(
            resultado.metricas["cobertura_l1_l2"], self.umbrales.cobertura_l1_l2
        )

    def test_golden_has_dev_holdout_split(self) -> None:
        dev = filtrar_casos_por_estrato(self.golden, "dev")
        holdout = filtrar_casos_por_estrato(self.golden, "holdout")
        self.assertGreater(len(dev), 1800)
        self.assertGreater(len(holdout), 400)
        self.assertEqual(len(dev) + len(holdout), 2357)
        overlap = {c.caso_id for c in dev} & {c.caso_id for c in holdout}
        self.assertEqual(overlap, set())

    def test_cascada_metrics_on_fixture(self) -> None:
        resultado, resultados = evaluar_golden_cascada(
            self.fixture,
            enable_l3=True,
            l3_mock=True,
            estrato_gate=None,
            estrato_eval=None,
            incluir_metricas_cascada=True,
        )
        cascada = metricas_cascada(resultados, self.fixture, estrato=None)
        self.assertIn("precision_cascada", cascada)
        self.assertEqual(resultado.metricas["total"], float(len(self.fixture.casos)))

    def test_l3_puro_metrics_on_fixture(self) -> None:
        resultado, resultados = evaluar_golden_cascada(
            self.fixture,
            enable_l3=True,
            l3_mock=True,
            l3_force_limit=3,
            estrato_gate=None,
            estrato_eval=None,
            incluir_metricas_cascada=True,
        )
        puro = metricas_l3_puro(resultados, self.fixture, estrato=None, l3_force_limit=3)
        self.assertEqual(puro["total_l3_puro"], 3.0)
        self.assertEqual(puro["ejecutados_l3_puro"], 3.0)
        self.assertIn("precision_l3_puro", resultado.metricas)
        self.assertIn("multi_hit_l3_puro", resultado.metricas)

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
