"""PT-5: publicar el tipo de proyecto al store canónico (enr_tipo_proyecto)."""

import tempfile
import unittest
from pathlib import Path

import polars as pl

from proyecttype.store_publish import (
    enricher_version,
    publish_to_store,
    to_enrichment_frame,
)


def _cascade_result(rows: list[dict]) -> pl.DataFrame:
    """DataFrame con el shape del output de la cascada."""
    return pl.DataFrame(rows)


class TestStorePublish(unittest.TestCase):
    def test_to_enrichment_frame_maps_and_filters(self) -> None:
        df = _cascade_result(
            [
                {"Codigo BIP": "30000001-0", "tipo_final_id": "TRANSPORTE.CICLOVIA",
                 "tipo_final_nombre": "Ciclovía", "score_final": 0.91, "nivel_final": 2},
                # Sin tipo asignado → se descarta.
                {"Codigo BIP": "30000002-0", "tipo_final_id": None,
                 "tipo_final_nombre": None, "score_final": 0.0, "nivel_final": 1},
            ]
        )
        out = to_enrichment_frame(df)
        self.assertIn("EBI_CODIGO", out.columns)
        self.assertIn("enricher_version", out.columns)
        self.assertEqual(out.height, 1)  # la fila sin tipo se filtró
        # EBI_CODIGO normalizado: sin el dígito verificador "-0" (joinable con EBI).
        self.assertEqual(out["EBI_CODIGO"][0], "30000001")

    def test_to_enrichment_frame_missing_columns_raises(self) -> None:
        df = pl.DataFrame({"Codigo BIP": ["1"]})  # faltan tipo_final_*
        with self.assertRaises(ValueError):
            to_enrichment_frame(df)

    def test_bip_code_normalized_for_join(self) -> None:
        """El sufijo verificador '-N' se quita → EBI_CODIGO joinable con CONSULTAS_EBI."""
        df = _cascade_result(
            [
                {"Codigo BIP": "30069417-0", "tipo_final_id": "X", "tipo_final_nombre": "x",
                 "score_final": 0.5, "nivel_final": 1},
                {"Codigo BIP": "  40056526-2  ", "tipo_final_id": "Y", "tipo_final_nombre": "y",
                 "score_final": 0.6, "nivel_final": 2},
            ]
        )
        out = to_enrichment_frame(df)
        self.assertEqual(set(out["EBI_CODIGO"].to_list()), {"30069417", "40056526"})

    def test_publish_ciclovia_roundtrip(self) -> None:
        """Caso del dueño: 'quiero los proyectos de ciclovía' — atributo creado y consultable."""
        from sni_commons.store import BipDataStore

        with tempfile.TemporaryDirectory() as d:
            df = _cascade_result(
                [
                    {"Codigo BIP": "30000001-0", "tipo_final_id": "TRANSPORTE.CICLOVIA",
                     "tipo_final_nombre": "Ciclovía", "score_final": 0.9, "nivel_final": 2},
                    {"Codigo BIP": "30000002-0", "tipo_final_id": "EDUCACION.JARDIN",
                     "tipo_final_nombre": "Jardín", "score_final": 0.8, "nivel_final": 1},
                ]
            )
            diag = publish_to_store(df, data_dir=d)
            self.assertEqual(diag.new, 2)

            # Consultar "ciclovías" desde el store (lo que haría SNI).
            store = BipDataStore(Path(d))
            rows = store.read_rows("enr_tipo_proyecto")
            ciclo = [r for r in rows if r["tipo_final_id"] == "TRANSPORTE.CICLOVIA"]
            self.assertEqual(len(ciclo), 1)
            self.assertEqual(ciclo[0]["EBI_CODIGO"], "30000001")  # normalizado
            self.assertEqual(ciclo[0]["enricher_version"], enricher_version())

    def test_publish_incremental_reclassify(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = [{"Codigo BIP": "1", "tipo_final_id": "A", "tipo_final_nombre": "a",
                     "score_final": 0.5, "nivel_final": 1}]
            publish_to_store(_cascade_result(base), data_dir=d)
            # Re-clasificar: el 1 cambia de tipo, entra el 2.
            updated = [
                {"Codigo BIP": "1", "tipo_final_id": "B", "tipo_final_nombre": "b",
                 "score_final": 0.7, "nivel_final": 3},
                {"Codigo BIP": "2", "tipo_final_id": "C", "tipo_final_nombre": "c",
                 "score_final": 0.6, "nivel_final": 2},
            ]
            diag = publish_to_store(_cascade_result(updated), data_dir=d)
            self.assertEqual((diag.new, diag.changed), (1, 1))

    def test_publish_dry_run_does_not_write(self) -> None:
        from sni_commons.store import BipDataStore

        with tempfile.TemporaryDirectory() as d:
            df = _cascade_result(
                [{"Codigo BIP": "1", "tipo_final_id": "A", "tipo_final_nombre": "a",
                  "score_final": 0.5, "nivel_final": 1}]
            )
            diag = publish_to_store(df, data_dir=d, dry_run=True)
            self.assertEqual(diag.new, 1)
            self.assertEqual(BipDataStore(Path(d)).row_count("enr_tipo_proyecto"), 0)


if __name__ == "__main__":
    unittest.main()
