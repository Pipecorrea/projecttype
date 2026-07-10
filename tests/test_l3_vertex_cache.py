"""Tests de Vertex Context Caching por subsector (L3)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from sni_commons.llm import CachedContext

from projecttype.l3_vertex_cache import (
    build_subsector_cache_contents,
    create_subsector_cache,
    unwrap_vertex_provider,
)
from projecttype.paths import DEFAULT_TAXONOMY
from projecttype.prompts import build_l3_user_prompt, load_l3_prompt_config
from projecttype.taxonomy import Taxonomia


class TestL3PromptSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)
        cls.cfg = load_l3_prompt_config()

    def test_static_payload_has_tipos_not_proyecto(self) -> None:
        tipos = self.tax.tipos_para(
            "RECURSOS HIDRICOS", "EVACUACION DISPOSICION FINAL AGUAS SERVIDAS"
        )
        self.assertTrue(tipos)
        static = json.loads(
            build_l3_user_prompt(
                sector="RECURSOS HIDRICOS",
                subsector="EVACUACION DISPOSICION FINAL AGUAS SERVIDAS",
                proyecto_text="NO DEBE APARECER",
                tipos=tipos,
                static_only=True,
            )
        )
        self.assertIn("tipos_validos", static)
        self.assertNotIn("proyecto", static)
        self.assertIn("contexto_adicional", static)
        guia = static["contexto_adicional"].get("guia_discriminante")
        self.assertIsNotNone(guia)
        self.assertIn("procedimiento", guia)

    def test_dynamic_payload_has_proyecto_not_tipos(self) -> None:
        tipos = self.tax.tipos_para("TRANSPORTE", "TRANSPORTE INTERURBANO")
        dynamic = json.loads(
            build_l3_user_prompt(
                sector="TRANSPORTE",
                subsector="TRANSPORTE INTERURBANO",
                proyecto_text="Mejoramiento ruta K-175",
                tipos=tipos,
                codigo_bip="20106461",
                l1_tipo_nombre="RUTA",
                l1_tipo_id="X",
                l1_estado="ambiguo",
                dynamic_only=True,
            )
        )
        self.assertEqual(dynamic["proyecto"], "Mejoramiento ruta K-175")
        self.assertEqual(dynamic["codigo_bip"], "20106461")
        self.assertIn("sugerencias_previas", dynamic)
        self.assertNotIn("tipos_validos", dynamic)

    def test_reglas_casetas_and_ruta_loaded(self) -> None:
        from projecttype.prompt_context import (
            _reglas_discriminantes,
            guia_discriminante_for_subsector,
        )

        _reglas_discriminantes.cache_clear()
        guia_c = guia_discriminante_for_subsector(
            "RECURSOS HIDRICOS", "EVACUACION DISPOSICION FINAL AGUAS SERVIDAS"
        )
        guia_r = guia_discriminante_for_subsector("TRANSPORTE", "TRANSPORTE INTERURBANO")
        self.assertIsNotNone(guia_c)
        self.assertIsNotNone(guia_r)
        self.assertGreaterEqual(len(guia_c.get("reglas_por_par") or []), 2)
        self.assertGreaterEqual(len(guia_r.get("reglas_por_par") or []), 1)


class TestVertexCacheHelpers(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)
        cls.cfg = load_l3_prompt_config()

    def test_unwrap_vertex_from_retry(self) -> None:
        from sni_commons.llm import VertexProvider
        from sni_commons.llm.retry import RetryProvider

        vertex = VertexProvider(project="p", location="us-central1")
        wrapped = RetryProvider(primary=vertex, max_retries=0)
        self.assertIs(unwrap_vertex_provider(wrapped), vertex)
        self.assertIs(unwrap_vertex_provider(vertex), vertex)
        self.assertIsNone(unwrap_vertex_provider(object()))

    def test_build_cache_contents(self) -> None:
        tipos = self.tax.tipos_para("TRANSPORTE", "TRANSPORTE INTERURBANO")
        system, contents = build_subsector_cache_contents(
            sector="TRANSPORTE",
            subsector="TRANSPORTE INTERURBANO",
            tipos=tipos,
            prompt_config=self.cfg,
        )
        self.assertIn("clasificador experto", system.lower())
        data = json.loads(contents)
        self.assertIn("tipos_validos", data)
        self.assertNotIn("proyecto", data)

    def test_create_subsector_cache_mocked(self) -> None:
        vertex = MagicMock()

        async def _create(**kwargs: object) -> CachedContext:
            return CachedContext(
                name="projects/p/locations/l/cachedContents/abc",
                display_name=str(kwargs.get("display_name") or ""),
                model="gemini-2.5-flash",
            )

        async def _delete(name: str) -> None:
            del name

        vertex.create_context_cache = _create
        vertex.delete_context_cache = _delete

        cache = create_subsector_cache(
            vertex,
            sector="TRANSPORTE",
            subsector="TRANSPORTE INTERURBANO",
            taxonomia=self.tax,
            prompt_config=self.cfg,
            model="gemini-2.5-flash",
        )
        self.assertEqual(cache.name, "projects/p/locations/l/cachedContents/abc")
        cache.close()


if __name__ == "__main__":
    unittest.main()
