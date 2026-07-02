"""Tests PT-9: metadatos de inferencia SC-13."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl

from proyecttype.classifier_cascade import ClassifierCascade
from proyecttype.inference_metadata import (
    EVIDENCIA_MAX_CHARS,
    prompt_version,
    truncate_evidencia,
)
from proyecttype.paths import DEFAULT_TAXONOMY, PROMPTS_DIR
from proyecttype.pipeline_cascade import classify_cascade_dataframe
from proyecttype.store_publish import publish_to_store, to_enrichment_frame


def _five_level_rows() -> pl.DataFrame:
    """Una fila por nivel L1/L2/L3/residual (+ extra L1)."""
    return pl.DataFrame(
        [
            {
                "Codigo BIP": "PT9-L1",
                "SECTOR": "CULTURA Y PATRIMONIO",
                "SUBSECTOR": "CULTURA",
                "NOMBRE": "REPOSICION BIBLIOTECA MUNICIPAL",
                "descripción": "CONSTRUCCION DE UN EDIFICIO PARA BIBLIOTECA COMUNAL",
                "justificacion_proyecto": "",
                "descriptor_1": "",
                "descriptor_2": "",
                "descriptor_3": "",
            },
            {
                "Codigo BIP": "PT9-L2",
                "SECTOR": "TRANSPORTE",
                "SUBSECTOR": "TRANSPORTE URBANO, VIALIDAD PEATONAL",
                "NOMBRE": "intervencion urbana mixta",
                "descripción": "mejoramiento de espacio publico con pavimentos y areas verdes en avenida",
                "justificacion_proyecto": "",
                "descriptor_1": "",
                "descriptor_2": "",
                "descriptor_3": "",
            },
            {
                "Codigo BIP": "PT9-L3",
                "SECTOR": "ENERGIA",
                "SUBSECTOR": "ALUMBRADO PUBLICO",
                "NOMBRE": "proyecto vago 0",
                "descripción": "algo",
                "justificacion_proyecto": "x",
                "descriptor_1": "",
                "descriptor_2": "",
                "descriptor_3": "",
            },
            {
                "Codigo BIP": "PT9-RES",
                "SECTOR": "ENERGIA",
                "SUBSECTOR": "ALUMBRADO PUBLICO",
                "NOMBRE": "proyecto vago 1",
                "descripción": "algo",
                "justificacion_proyecto": "x",
                "descriptor_1": "",
                "descriptor_2": "",
                "descriptor_3": "",
            },
            {
                "Codigo BIP": "PT9-RES2",
                "SECTOR": "RECURSOS HIDRICOS",
                "SUBSECTOR": "AGUA POTABLE",
                "NOMBRE": "SISTEMA DE RIEGO COMUNIDAD AGRICOLA",
                "descripción": "riego agricola",
                "justificacion_proyecto": "",
                "descriptor_1": "",
                "descriptor_2": "",
                "descriptor_3": "",
            },
        ]
    )


class TestInferenceMetadata(unittest.TestCase):
    def test_prompt_version_changes_on_yaml_edit(self) -> None:
        before = prompt_version()
        l3_path = PROMPTS_DIR / "l3.yaml"
        original = l3_path.read_text(encoding="utf-8")
        try:
            l3_path.write_text(original + "\n# pt9-test-byte\n", encoding="utf-8")
            after = prompt_version()
            self.assertNotEqual(before, after)
        finally:
            l3_path.write_text(original, encoding="utf-8")

    def test_truncate_evidencia_max_500(self) -> None:
        long_cot = "x" * 800
        out = truncate_evidencia(long_cot)
        self.assertLessEqual(len(out), EVIDENCIA_MAX_CHARS)

    def test_cascade_publishes_all_sc13_columns(self) -> None:
        cascade = ClassifierCascade.from_yaml(
            DEFAULT_TAXONOMY,
            enable_l3=True,
            l3_mock=True,
        )
        result = classify_cascade_dataframe(
            _five_level_rows(),
            cascade,
            l3_model="mock-llm",
        )
        frame = to_enrichment_frame(result)
        required = {
            "nivel_asignacion",
            "confianza",
            "evidencia_resumen",
            "modelo",
            "prompt_version",
            "taxonomy_hash",
            "enricher_version",
        }
        self.assertTrue(required.issubset(set(frame.columns)))
        self.assertGreaterEqual(frame.height, 1)

        niveles = set(frame["nivel_asignacion"].to_list())
        self.assertIn("L1", niveles)

        for evidencia in frame["evidencia_resumen"].to_list():
            self.assertLessEqual(len(evidencia or ""), EVIDENCIA_MAX_CHARS)

        l1_rows = frame.filter(pl.col("nivel_asignacion") == "L1")
        if l1_rows.height:
            self.assertEqual(l1_rows["modelo"][0], "n/a")
            self.assertIsNotNone(l1_rows["confianza"][0])

    def test_publish_roundtrip_with_metadata(self) -> None:
        cascade = ClassifierCascade.from_yaml(
            DEFAULT_TAXONOMY,
            enable_l3=True,
            l3_mock=True,
        )
        result = classify_cascade_dataframe(
            _five_level_rows().head(2),
            cascade,
            l3_model="mock-llm",
        )
        with tempfile.TemporaryDirectory() as tmp:
            diag = publish_to_store(result, data_dir=tmp)
            self.assertGreaterEqual(diag.new, 1)
            from sni_commons.store import BipDataStore

            rows = BipDataStore(Path(tmp)).read_rows("enr_tipo_proyecto")
            self.assertTrue(rows)
            row = rows[0]
            self.assertIsNotNone(row.get("prompt_version"))
            self.assertIsNotNone(row.get("taxonomy_hash"))
            self.assertIn(row.get("nivel_asignacion"), {"L1", "L2", "L3", "residual"})


if __name__ == "__main__":
    unittest.main()
