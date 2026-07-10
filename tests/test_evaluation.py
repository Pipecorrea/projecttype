"""Tests de evaluación L1 vs etiquetado manual."""

from __future__ import annotations

import unittest

from projecttype.evaluation import NivelMatch, clasificar_match, manual_en_tipos_l3
from projecttype.text_utils import normalize_tipo_name


class TestEvaluation(unittest.TestCase):
    def test_estandar_vs_estandard_es_exacta(self) -> None:
        nivel = clasificar_match("GIMNASIO ESTANDARD", "GIMNASIO ESTANDAR", l1_estado="asignado")
        self.assertEqual(nivel, NivelMatch.COINCIDENCIA_EXACTA)

    def test_normalize_tipo_name_estandard(self) -> None:
        self.assertEqual(
            normalize_tipo_name("GIMNASIO ESTANDARD"),
            normalize_tipo_name("GIMNASIO ESTANDAR"),
        )

    def test_manual_en_tipos_l3_principal(self) -> None:
        self.assertTrue(
            manual_en_tipos_l3(
                "CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA",
                [],
                "CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA",
            )
        )

    def test_manual_en_tipos_l3_secundario(self) -> None:
        self.assertTrue(
            manual_en_tipos_l3(
                "RED DE AGUA POTABLE Y PLANTA DE TRATAMIENTO",
                ["CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA"],
                "CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA",
            )
        )

    def test_manual_en_tipos_l3_miss(self) -> None:
        self.assertFalse(
            manual_en_tipos_l3(
                "RED DE AGUA POTABLE Y PLANTA DE TRATAMIENTO",
                [],
                "PUENTE URBANO",
            )
        )


if __name__ == "__main__":
    unittest.main()
