"""PT-14: enrich --from-selection contra sel_tipo_proyecto_<id>."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl
from typer.testing import CliRunner

from projecttype.cli import app
from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.store_publish import enricher_version


def _seed_store(base: Path, *, seleccion_id: str = "testsel") -> None:
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT, SEL_PROYECTOS_CONTRACT
    from sni_commons.store import BipDataStore

    ebi = pl.DataFrame(
        {
            "EBI_CODIGO": [str(i) for i in range(1, 6)],
            "SOL_CLAVE": ["1"] * 5,
            "EBI_NOMBRE": [f"P{i}" for i in range(1, 6)],
            "SEC_CLAVE": ["10"] * 5,
            "SBS_CLAVE": ["1061"] * 5,
            "EBI_DESCRIPCION": ["d"] * 5,
            "EBI_JUSTIFICACION": [None] * 5,
        }
    )
    store = BipDataStore(base)
    store.upsert_dataframe("CONSULTAS_EBI", ebi, key_cols=["EBI_CODIGO", "SOL_CLAVE"], writer="test")

    sel_rows = []
    for code in ["1", "2", "3", "4", "5"]:
        sel_rows.append(
            {
                "EBI_CODIGO": code,
                "NOMBRE": f"P{code}",
                "SECTOR": "Salud",
                "REGION": "Metropolitana",
                "seleccion_id": seleccion_id,
                "criterio_json": "{}",
                "creado_en": "2026-07-04",
            }
        )
    sel_df = pl.DataFrame(sel_rows)
    SEL_PROYECTOS_CONTRACT.validate(sel_df.columns)
    store.upsert_dataframe(
        f"sel_tipo_proyecto_{seleccion_id}",
        sel_df,
        contract=SEL_PROYECTOS_CONTRACT,
        key_cols=["seleccion_id", "EBI_CODIGO"],
        writer="test",
    )

    tax = taxonomy_hash()
    prompt = prompt_version()
    enr = pl.DataFrame(
        {
            "EBI_CODIGO": ["1", "2", "3"],
            "tipo_final_id": ["A", "A", "A"],
            "tipo_final_nombre": ["A", "A", "A"],
            "score_final": [0.9, 0.9, 0.9],
            "nivel_final": [1, 1, 1],
            "nivel_asignacion": ["L1"] * 3,
            "confianza": [0.9] * 3,
            "evidencia_resumen": [""] * 3,
            "modelo": ["n/a"] * 3,
            "prompt_version": [prompt] * 3,
            "taxonomy_hash": [tax] * 3,
            "enricher_version": [enricher_version()] * 3,
        }
    )
    store.upsert_dataframe(
        "enr_tipo_proyecto",
        enr,
        contract=ENR_TIPO_PROYECTO_CONTRACT,
        key_cols=["EBI_CODIGO"],
        writer="test",
        mark_missing=False,
    )


class TestFromSelection(unittest.TestCase):
    def test_load_selection_bips(self) -> None:
        from projecttype.store_input import load_selection_bips

        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_store(base, seleccion_id="abc")
            bips = load_selection_bips("abc", base)
            self.assertEqual(sorted(bips), ["1", "2", "3", "4", "5"])

    def test_seleccion_inexistente_error_claro(self) -> None:
        from projecttype.store_input import load_selection_bips

        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError) as ctx:
                load_selection_bips("noexiste", d)
            self.assertIn("snii seleccion-proyectos", str(ctx.exception))

    def test_dry_run_solo_pendientes(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _seed_store(d, seleccion_id="abc")
            runner = CliRunner()
            r = runner.invoke(
                app,
                ["enrich", "--from-selection", "abc", "--dry-run", "--data-dir", d],
            )
            self.assertEqual(r.exit_code, 0)
            self.assertIn("a clasificar: 2", r.stdout)
            self.assertIn("saltados: 3", r.stdout)

    def test_flags_excluyentes(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            ["enrich", "--from-store", "--from-selection", "x"],
        )
        self.assertNotEqual(r.exit_code, 0)

    def test_publish_parcial_registra_source(self) -> None:
        from sni_commons.store import BipDataStore

        fake_result = pl.DataFrame(
            {
                "Codigo BIP": ["4"],
                "tipo_final_id": ["ENERGIA.ALUMBRADO_PUBLICO.ALUMBRADO_PUBLICO"],
                "tipo_final_nombre": ["ALUMBRADO PUBLICO"],
                "score_final": [0.8],
                "nivel_final": [1],
            }
        )
        with tempfile.TemporaryDirectory() as d:
            _seed_store(d, seleccion_id="abc")
            with patch("projecttype.pipeline_cascade.classify_cascade_dataframe", return_value=fake_result):
                runner = CliRunner()
                r = runner.invoke(
                    app,
                    ["enrich", "--from-selection", "abc", "--data-dir", d],
                )
            self.assertEqual(r.exit_code, 0, r.stdout)
            store = BipDataStore(Path(d))
            rows = store.read_rows("enr_tipo_proyecto", only_present=True)
            codes = {r["EBI_CODIGO"] for r in rows}
            self.assertEqual(codes, {"1", "2", "3", "4"})
            loads = store.read_rows("_loads", only_present=False)
            sources = [r.get("source") for r in loads if r.get("table_name") == "enr_tipo_proyecto"]
            self.assertTrue(any(s == "seleccion:abc" for s in sources))


if __name__ == "__main__":
    unittest.main()
