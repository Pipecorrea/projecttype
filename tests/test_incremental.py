"""PT-7: anti-join incremental contra enr_tipo_proyecto vigente."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import polars as pl
from typer.testing import CliRunner

from projecttype.cli import app
from projecttype.incremental import filter_pending
from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.store_publish import enricher_version, publish_to_store


def _seed_ebi(base: Path) -> None:
    from sni_commons.store import BipDataStore

    df = pl.DataFrame(
        {
            "EBI_CODIGO": ["100", "200", "300", "400", "500"],
            "SOL_CLAVE": ["1", "1", "1", "1", "1"],
            "EBI_NOMBRE": [f"P{i}" for i in range(1, 6)],
            "SEC_CLAVE": ["10", "10", "10", "10", "10"],
            "SBS_CLAVE": ["1061", "1061", "1061", "1061", "1061"],
            "EBI_DESCRIPCION": ["d"] * 5,
            "EBI_JUSTIFICACION": [None] * 5,
        }
    )
    BipDataStore(base).upsert_dataframe(
        "CONSULTAS_EBI", df, key_cols=["EBI_CODIGO", "SOL_CLAVE"], writer="test"
    )


def _cascade_row(code: str, tipo: str = "A") -> dict:
    return {
        "Codigo BIP": code,
        "tipo_final_id": tipo,
        "tipo_final_nombre": tipo,
        "score_final": 0.9,
        "nivel_final": 1,
    }


def _publish_enr(base: Path, codes: list[str], *, tax_hash: str, prompt_ver: str) -> None:
    rows = [_cascade_row(c) for c in codes]
    df = pl.DataFrame(rows)
    publish_to_store(
        df,
        data_dir=base,
        mark_missing=False,
    )
    # Metadatos SC-13 ya van en publish; forzamos tax_hash distinto vía re-publish si hace falta
    store_df = pl.DataFrame(
        {
            "EBI_CODIGO": codes,
            "tipo_final_id": ["A"] * len(codes),
            "tipo_final_nombre": ["A"] * len(codes),
            "score_final": [0.9] * len(codes),
            "nivel_final": [1] * len(codes),
            "nivel_asignacion": ["L1"] * len(codes),
            "confianza": [0.9] * len(codes),
            "evidencia_resumen": [""] * len(codes),
            "modelo": ["n/a"] * len(codes),
            "prompt_version": [prompt_ver] * len(codes),
            "taxonomy_hash": [tax_hash] * len(codes),
            "enricher_version": [enricher_version()] * len(codes),
        }
    )
    from sni_commons.contracts import ENR_TIPO_PROYECTO_CONTRACT
    from sni_commons.store import BipDataStore

    BipDataStore(base).upsert_dataframe(
        "enr_tipo_proyecto",
        store_df,
        contract=ENR_TIPO_PROYECTO_CONTRACT,
        key_cols=["EBI_CODIGO"],
        writer="test",
        mark_missing=False,
    )


class TestIncremental(unittest.TestCase):
    def test_solo_pendientes_cuando_hay_vigentes(self) -> None:
        from projecttype.store_input import load_cascade_input_from_store

        tax = taxonomy_hash()
        prompt = prompt_version()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base)
            _publish_enr(base, ["100", "200", "300"], tax_hash=tax, prompt_ver=prompt)
            inp = load_cascade_input_from_store(base)
            split = filter_pending(
                inp,
                data_dir=base,
                tax_hash=tax,
                prompt_ver=prompt,
                enricher_ver=enricher_version(),
            )
            self.assertEqual(split.pendientes.height, 2)
            self.assertEqual(split.saltados.height, 3)
            pending_codes = set(split.pendientes["Codigo BIP"].to_list())
            self.assertEqual(pending_codes, {"400", "500"})

    def test_taxonomy_hash_distinto_reclasifica_todo(self) -> None:
        from projecttype.store_input import load_cascade_input_from_store

        tax = taxonomy_hash()
        prompt = prompt_version()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base)
            _publish_enr(base, ["100", "200", "300"], tax_hash=tax, prompt_ver=prompt)
            inp = load_cascade_input_from_store(base)
            split = filter_pending(
                inp,
                data_dir=base,
                tax_hash="otro_hash",
                prompt_ver=prompt,
                enricher_ver=enricher_version(),
            )
            self.assertEqual(split.pendientes.height, 5)
            self.assertEqual(split.saltados.height, 0)

    def test_publish_parcial_no_toca_terceros(self) -> None:
        from sni_commons.store import BipDataStore

        tax = taxonomy_hash()
        prompt = prompt_version()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base)
            _publish_enr(base, ["100", "200", "300"], tax_hash=tax, prompt_ver=prompt)
            publish_to_store(
                pl.DataFrame([_cascade_row("400")]),
                data_dir=base,
                mark_missing=False,
            )
            rows = BipDataStore(base).read_rows("enr_tipo_proyecto", only_present=True)
            codes = {r["EBI_CODIGO"] for r in rows}
            self.assertEqual(codes, {"100", "200", "300", "400"})

    def test_cli_incremental_dry_run(self) -> None:
        tax = taxonomy_hash()
        prompt = prompt_version()
        with tempfile.TemporaryDirectory() as d:
            base = Path(d)
            _seed_ebi(base)
            _publish_enr(base, ["100", "200", "300"], tax_hash=tax, prompt_ver=prompt)
            runner = CliRunner()
            r = runner.invoke(
                app,
                ["enrich", "--from-store", "--incremental", "--dry-run", "--data-dir", d],
            )
            self.assertEqual(r.exit_code, 0)
            self.assertIn("a clasificar: 2", r.stdout)
            self.assertIn("saltados: 3", r.stdout)


if __name__ == "__main__":
    unittest.main()
