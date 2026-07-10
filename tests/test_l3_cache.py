"""Tests PT-15: caché L3 prompt-aware."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from projecttype.l3_cache import L3CacheEntry, L3ResultCache
from projecttype.scorer import EstadoClasificacion, ResultadoClasificacion


def _sample_result() -> ResultadoClasificacion:
    return ResultadoClasificacion(
        estado=EstadoClasificacion.ASIGNADO,
        tipo_id="T1",
        tipo_nombre="Tipo Uno",
        score=0.9,
        nivel=3,
        sector_resuelto="ENERGIA",
        subsector_resuelto="ALUMBRADO PUBLICO",
        tipos_secundarios_nombres=["Tipo Dos"],
        multi_tipo=True,
    )


class TestL3CachePromptAware(unittest.TestCase):
    def test_cache_hit_on_triple_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l3_cache.jsonl"
            cache = L3ResultCache(path, model="mock-llm", prompt_version="abc123")
            cache.put("30000001", _sample_result(), "razon test")
            cache.save()

            reloaded = L3ResultCache(path, model="mock-llm", prompt_version="abc123")
            entry = reloaded.get("30000001")
            self.assertIsNotNone(entry)
            self.assertEqual(reloaded.hits, 1)
            self.assertEqual(entry.l3_tipo_id, "T1")
            self.assertEqual(entry.l3_tipos_secundarios_nombres, "Tipo Dos")
            self.assertTrue(entry.l3_multi_tipo)

    def test_cache_miss_when_prompt_version_differs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l3_cache.jsonl"
            cache = L3ResultCache(path, model="mock-llm", prompt_version="prompt_v1")
            cache.put("30000002", _sample_result(), "razon test")
            cache.save()

            other = L3ResultCache(path, model="mock-llm", prompt_version="prompt_v2")
            self.assertIsNone(other.get("30000002"))
            self.assertEqual(other.hits, 0)

    def test_v2_entries_are_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "l3_cache.jsonl"
            legacy = L3CacheEntry(
                codigo_bip="30000003",
                model="mock-llm",
                prompt_version="",
                l3_estado="asignado",
                l3_tipo_id="T1",
                l3_tipo_nombre="Tipo Uno",
                l3_confianza=0.9,
                l3_razonamiento="legacy",
                cache_version="2",
            )
            path.write_text(
                __import__("json").dumps(legacy.to_dict()) + "\n",
                encoding="utf-8",
            )
            cache = L3ResultCache(path, model="mock-llm", prompt_version="abc123")
            self.assertIsNone(cache.get("30000003"))


if __name__ == "__main__":
    unittest.main()
