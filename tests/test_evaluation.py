"""Tests de evaluación L1 vs etiquetado manual."""

from __future__ import annotations

import unittest

from projecttype.evaluation import NivelMatch, clasificar_match
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


if __name__ == "__main__":
    unittest.main()
