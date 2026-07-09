"""PT-6: input de la cascada desde el store (CONSULTAS_EBI sintético)."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import polars as pl


def _seed_store(base: Path) -> None:
    from sni_commons.store import BipDataStore

    df = pl.DataFrame(
        {
            # 30069417 con dos solicitudes: debe ganar la más reciente (20)
            "EBI_CODIGO": ["30069417", "30069417", "40000001"],
            "SOL_CLAVE": ["10", "20", "5"],
            "EBI_NOMBRE": ["REPOSICION POSTA VIEJA", "REPOSICION POSTA NUEVA", "CONSTRUCCION RUTA X"],
            "SEC_CLAVE": ["10", "10", "6"],
            "SBS_CLAVE": ["1061", "1061", "1061"],
            "EBI_DESCRIPCION": ["desc vieja", "desc nueva", "desc ruta"],
            "EBI_JUSTIFICACION": [None, "justif", "j2"],
        }
    )
    BipDataStore(base).upsert_dataframe(
        "CONSULTAS_EBI", df, key_cols=["EBI_CODIGO", "SOL_CLAVE"], writer="test"
    )


class TestStoreInput(unittest.TestCase):
    def test_mapea_dedup_y_nombres(self) -> None:
        from projecttype.store_input import load_cascade_input_from_store

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _seed_store(base)
            out = load_cascade_input_from_store(base)

        self.assertEqual(out.height, 2)  # dedupe por proyecto
        row = out.filter(pl.col("Codigo BIP") == "30069417").row(0, named=True)
        self.assertEqual(row["NOMBRE"], "REPOSICION POSTA NUEVA")  # SOL_CLAVE 20 gana
        self.assertEqual(row["SECTOR"], "SALUD")  # SEC_CLAVE 10 → nombre
        self.assertEqual(row["SUBSECTOR"], "AGRICULTURA")  # SBS_CLAVE 1061 → nombre
        self.assertEqual(row["justificacion_proyecto"], "justif")
        self.assertEqual(row["descripción"], "desc nueva")
        self.assertEqual(row["descriptor_1"], "")
        # columnas exactas que la cascada espera
        self.assertEqual(
            out.columns,
            [
                "Codigo BIP", "NOMBRE", "SECTOR", "SUBSECTOR",
                "justificacion_proyecto", "descripción",
                "descriptor_1", "descriptor_2", "descriptor_3",
            ],
        )

    def test_limit(self) -> None:
        from projecttype.store_input import load_cascade_input_from_store

        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            _seed_store(base)
            out = load_cascade_input_from_store(base, limit=1)
        self.assertEqual(out.height, 1)

    def test_sin_data_dir_error_claro(self) -> None:
        import os

        from projecttype.store_input import load_cascade_input_from_store

        old = os.environ.pop("BIP_DATA_DIR", None)
        try:
            with self.assertRaises(RuntimeError):
                load_cascade_input_from_store(None)
        finally:
            if old is not None:
                os.environ["BIP_DATA_DIR"] = old


if __name__ == "__main__":
    unittest.main()
