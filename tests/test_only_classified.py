"""PT-18: ``enrich --from-store --only-classified`` — re-publish acotado.

Restringe la clasificación a los EBI_CODIGO que YA existen en
``enr_tipo_proyecto`` (para re-publicar con metadatos frescos sin recorrer el
universo completo de CONSULTAS_EBI). Cubre el helper puro
``_load_existing_classified_bips`` y el cableado del flag en el CLI.
"""

from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import polars as pl
import typer
from typer.testing import CliRunner

from projecttype.cli import _load_existing_classified_bips, app
from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.store_publish import enricher_version


def _seed_ebi(base: Path, codes: list[str]) -> None:
    from sni_commons.store import BipDataStore

    n = len(codes)
    df = pl.DataFrame(
        {
            "EBI_CODIGO": codes,
            "SOL_CLAVE": ["1"] * n,
            "EBI_NOMBRE": [f"P{c}" for c in codes],
            "SEC_CLAVE": ["10"] * n,
            "SBS_CLAVE": ["1061"] * n,
            "EBI_DESCRIPCION": ["d"] * n,
            "EBI_JUSTIFICACION": [None] * n,
        }
    )
    BipDataStore(base).upsert_dataframe(
        "CONSULTAS_EBI", df, key_cols=["EBI_CODIGO", "SOL_CLAVE"], writer="test"
    )


def _publish_enr(base: Path, codes: list[str]) -> None:
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT
    from sni_commons.store import BipDataStore

    tipo = "ENERGIA.ALUMBRADO_PUBLICO.ALUMBRADO_PUBLICO"
    n = len(codes)
    store_df = pl.DataFrame(
        {
            "EBI_CODIGO": codes,
            "tipo_final_id": [tipo] * n,
            "tipo_final_nombre": [tipo] * n,
            "score_final": [0.9] * n,
            "nivel_final": [1] * n,
            "nivel_asignacion": ["L1"] * n,
            "confianza": [0.9] * n,
            "evidencia_resumen": [""] * n,
            "modelo": ["n/a"] * n,
            "prompt_version": [prompt_version()] * n,
            "taxonomy_hash": [taxonomy_hash()] * n,
            "enricher_version": [enricher_version()] * n,
        }
    )
    BipDataStore(base).upsert_dataframe(
        "enr_tipo_proyecto",
        store_df,
        contract=ENR_TIPO_PROYECTO_CONTRACT,
        key_cols=["EBI_CODIGO"],
        writer="test",
        mark_missing=False,
    )


class TestLoadExistingClassifiedBips(unittest.TestCase):
    def test_sin_data_dir_ni_env_error_claro(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(typer.BadParameter) as ctx:
                _load_existing_classified_bips(None)
        self.assertIn("BIP_DATA_DIR", str(ctx.exception))

    def test_tabla_inexistente_error_claro(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            _seed_ebi(Path(d), ["100"])  # store existe, pero sin enr_tipo_proyecto
            with self.assertRaises(typer.BadParameter) as ctx:
                _load_existing_classified_bips(d)
        self.assertIn("no existe", str(ctx.exception))

    def test_devuelve_codigos_vigentes_ordenados_y_dedup(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base, ["100", "200", "300", "400", "500"])
            _publish_enr(base, ["300", "100", "200"])
            bips = _load_existing_classified_bips(d)
        self.assertEqual(bips, ["100", "200", "300"])

    def test_toma_bip_data_dir_del_entorno(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base, ["100", "200"])
            _publish_enr(base, ["100", "200"])
            with patch.dict(os.environ, {"BIP_DATA_DIR": d}, clear=True):
                bips = _load_existing_classified_bips(None)
        self.assertEqual(bips, ["100", "200"])


class TestOnlyClassifiedCli(unittest.TestCase):
    def test_restringe_a_los_ya_clasificados(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base, ["100", "200", "300", "400", "500"])
            _publish_enr(base, ["100", "200", "300"])
            runner = CliRunner()
            r = runner.invoke(
                app,
                ["enrich", "--from-store", "--only-classified", "--dry-run", "--data-dir", d],
            )
        self.assertEqual(r.exit_code, 0, r.stdout)
        self.assertIn("Restringiendo a 3 EBI_CODIGO", r.stdout)

    def test_excluyente_con_from_selection(self) -> None:
        runner = CliRunner()
        r = runner.invoke(
            app,
            ["enrich", "--from-selection", "abc", "--only-classified"],
        )
        self.assertNotEqual(r.exit_code, 0)


if __name__ == "__main__":
    unittest.main()
