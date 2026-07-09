"""Tests de minería few-shot."""

from __future__ import annotations

import unittest

from projecttype.evaluation import NivelMatch
from projecttype.few_shot_mining import (
    extract_evidencia,
    mine_from_files,
    resolve_manual_tipo,
)
from projecttype.paths import DEFAULT_OUTPUT_CASCADE_CSV, DEFAULT_SUBMUESTRA, DEFAULT_TAXONOMY
from projecttype.taxonomy import Taxonomia


class TestFewShotMining(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)

    def test_resolve_manual_tipo(self) -> None:
        tipo = resolve_manual_tipo(
            self.tax,
            sector="ENERGIA",
            subsector="ALUMBRADO PUBLICO",
            tipo_manual="ALUMBRADO PUBLICO",
        )
        self.assertIsNotNone(tipo)
        self.assertIn("ALUMBRADO", tipo.nombre)

    def test_extract_evidencia(self) -> None:
        tipo = self.tax.tipos_para("ENERGIA", "ALUMBRADO PUBLICO")[0]
        ev = extract_evidencia("Mejoramiento alumbrado publico sector centro", tipo)
        self.assertGreater(len(ev), 0)

    def test_mine_from_files(self) -> None:
        if not DEFAULT_OUTPUT_CASCADE_CSV.exists():
            self.skipTest("sin resultados cascada")
        if not DEFAULT_SUBMUESTRA.exists():
            self.skipTest("sin Submuestra_tp.xlsx (ver PT-10 / golden fixture)")
        examples = mine_from_files(
            resultados_path=DEFAULT_OUTPUT_CASCADE_CSV,
            submuestra_path=DEFAULT_SUBMUESTRA,
            taxonomy_path=DEFAULT_TAXONOMY,
            max_per_subsector=1,
            max_total=5,
        )
        self.assertGreater(len(examples), 0)
        self.assertTrue(all(ex.respuesta.get("tipo_id") for ex in examples))
        self.assertIn(
            examples[0].nivel_match_l1,
            {
                NivelMatch.DISCREPANCIA.value,
                NivelMatch.SIN_CLASIFICACION_L1.value,
                NivelMatch.COINCIDENCIA_PARCIAL.value,
            },
        )


if __name__ == "__main__":
    unittest.main()
