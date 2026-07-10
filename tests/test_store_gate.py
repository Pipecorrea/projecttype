"""Tests PT-18: gate de publicación antes del upsert."""

from __future__ import annotations

import tempfile
import unittest

import polars as pl

from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.store_gate import (
    StoreGateRejectedError,
    aplicar_gate,
    validar_fila_tipo,
)
from projecttype.store_publish import enricher_version, publish_to_store, to_enrichment_frame

_TIPO_VALIDO = "ENERGIA.ALUMBRADO_PUBLICO.ALUMBRADO_PUBLICO"


def _cascade_row(
    *,
    codigo_bip: str = "30000001",
    tipo_id: str = _TIPO_VALIDO,
    nivel_final: int = 1,
    estado_final: str = "asignado",
    l1_score: float = 1.5,
    l1_evidencia: str = "keyword match",
) -> dict[str, object]:
    return {
        "Codigo BIP": codigo_bip,
        "tipo_final_id": tipo_id,
        "tipo_final_nombre": "ALUMBRADO PUBLICO",
        "score_final": l1_score,
        "nivel_final": nivel_final,
        "estado_final": estado_final,
        "l1_estado": "asignado",
        "l1_score": l1_score,
        "l1_evidencia": l1_evidencia,
        "l2_estado": None,
        "l2_tipo_id": None,
        "l2_tipo_nombre": None,
        "l2_similitud": None,
        "l3_estado": None,
        "l3_confianza": None,
        "l3_razonamiento": "",
    }


class TestStoreGate(unittest.TestCase):
    def test_clave_no_canonica_rechazada(self) -> None:
        frame = to_enrichment_frame(pl.DataFrame([_cascade_row(codigo_bip="30000001-0")]))
        resultado = aplicar_gate(frame)
        self.assertEqual(resultado.filas_validas.height, 0)
        self.assertEqual(len(resultado.filas_rechazadas), 1)
        self.assertIn("clave_no_canonica", resultado.filas_rechazadas[0][1])
        self.assertEqual(resultado.resumen.get("clave_no_canonica"), 1)

    def test_fila_limpia_pasa(self) -> None:
        frame = to_enrichment_frame(pl.DataFrame([_cascade_row()]))
        resultado = aplicar_gate(frame)
        self.assertEqual(resultado.filas_validas.height, 1)
        self.assertEqual(resultado.filas_rechazadas, ())
        self.assertEqual(resultado.resumen, {})

    def test_revisor_ausente_con_validacion(self) -> None:
        row = {
            "EBI_CODIGO": "30000001",
            "_ebi_raw": "30000001",
            "tipo_final_id": _TIPO_VALIDO,
            "nivel_asignacion": "humano",
            "evidencia_resumen": "ok",
            "modelo": "n/a",
            "prompt_version": prompt_version(),
            "taxonomy_hash": taxonomy_hash(),
            "enricher_version": enricher_version(),
            "validado_por_humano": True,
            "revisor": "",
        }
        motivos = validar_fila_tipo(row)
        self.assertIn("revisor_ausente_con_validacion", motivos)

    def test_publish_to_store_aborta_con_gate(self) -> None:
        bad = pl.DataFrame([_cascade_row(codigo_bip="30000001-0")])
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(StoreGateRejectedError) as ctx:
                publish_to_store(bad, data_dir=tmp)
            self.assertIn("clave_no_canonica", ctx.exception.resultado.resumen)


if __name__ == "__main__":
    unittest.main()
