"""Resiliencia del lote L3: un fallo transitorio del LLM no aborta la cascada."""

from __future__ import annotations

import unittest

import polars as pl

from projecttype.classifier_cascade import ClassifierCascade
from projecttype.llm_client import MockLLMClient
from projecttype.paths import DEFAULT_TAXONOMY
from projecttype.pipeline_cascade import classify_cascade_dataframe


def _residual_rows(n: int) -> pl.DataFrame:
    # Nombres vagos en un subsector con taxonomía → residual en L1 y L2,
    # así las n filas caen a L3 (verificado contra la taxonomía real).
    rows = [
        {
            "Codigo BIP": f"BIP{i}",
            "SECTOR": "ENERGIA",
            "SUBSECTOR": "ALUMBRADO PUBLICO",
            "NOMBRE": f"proyecto vago {i}",
            "descripción": "algo",
            "justificacion_proyecto": "x",
            "descriptor_1": "",
            "descriptor_2": "",
            "descriptor_3": "",
        }
        for i in range(n)
    ]
    return pl.DataFrame(rows)


class TestPipelineCascadeL3Resilience(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.cascade = ClassifierCascade.from_yaml(
            DEFAULT_TAXONOMY, enable_l3=True, l3_mock=True
        )

    def test_llm_error_in_one_row_does_not_abort_batch(self) -> None:
        # El cliente L3 falla en la 2.ª llamada (orden = BIP0, BIP1, BIP2, BIP3).
        self.cascade.l3.client = MockLLMClient(fail_on_calls=frozenset({2}))

        df = _residual_rows(4)
        result = classify_cascade_dataframe(df, self.cascade, l3_model="mock")

        by_codigo = {row["Codigo BIP"]: row for row in result.to_dicts()}

        # Las 3 filas sanas se clasificaron en L3 igual que sin el fallo.
        for codigo in ("BIP0", "BIP2", "BIP3"):
            self.assertEqual(by_codigo[codigo]["l3_estado"], "ambiguo")
            self.assertNotIn(
                "Error LLM", by_codigo[codigo]["l3_razonamiento"] or ""
            )

        # La fila que falló quedó como residual marcada, sin tumbar el lote.
        fallida = by_codigo["BIP1"]
        self.assertEqual(fallida["l3_estado"], "sin_match")
        self.assertTrue(
            (fallida["l3_razonamiento"] or "").startswith("Error LLM (lote protegido)")
        )


if __name__ == "__main__":
    unittest.main()
