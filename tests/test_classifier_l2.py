"""Tests básicos del clasificador Nivel 2."""

from __future__ import annotations

import unittest

from projecttype import ClassifierL2, EstadoClasificacion
from projecttype.paths import DEFAULT_TAXONOMY


class TestClassifierL2(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.clf = ClassifierL2.from_yaml(DEFAULT_TAXONOMY)

    def test_transporte_urbana_asignado(self) -> None:
        """Caso residual en L1 típico: L2 asigna por similitud semántica."""
        result = self.clf.classify_row(
            sector="TRANSPORTE",
            subsector="TRANSPORTE URBANO, VIALIDAD PEATONAL",
            nombre="intervencion urbana mixta",
            descripcion=(
                "mejoramiento de espacio publico con pavimentos y areas verdes en avenida"
            ),
        )
        self.assertIn(
            result.estado,
            (EstadoClasificacion.ASIGNADO, EstadoClasificacion.AMBIGUO),
        )
        self.assertIsNotNone(result.tipo_nombre)
        self.assertGreaterEqual(result.score, 0.48)

    def test_sin_taxonomia(self) -> None:
        result = self.clf.classify_row(sector="SECTOR INEXISTENTE", subsector="X")
        self.assertEqual(result.estado, EstadoClasificacion.SIN_TAXONOMIA)

    def test_batch_misma_longitud(self) -> None:
        rows = [
            {
                "NOMBRE": "intervencion urbana mixta",
                "descripción": "mejoramiento de espacio publico",
            },
            {
                "NOMBRE": "proyecto vago",
                "descripción": "algo",
            },
        ]
        results = self.clf.classify_rows_batch(
            rows,
            sector="TRANSPORTE",
            subsector="TRANSPORTE URBANO, VIALIDAD PEATONAL",
        )
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].nivel, 2)


if __name__ == "__main__":
    unittest.main()
