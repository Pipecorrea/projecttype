"""Tests del clasificador L3."""

from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock

from proyecttype.classifier_l3 import (
    ClassifierL3,
    L3Config,
    parse_l3_response,
)
from proyecttype.llm_client import MockLLMClient, OllamaClient, _extract_json
from proyecttype.paths import DEFAULT_TAXONOMY
from proyecttype.prompts import build_l3_user_prompt, format_tipo_option
from proyecttype.scorer import EstadoClasificacion
from proyecttype.taxonomy import Taxonomia


class TestL3Parsing(unittest.TestCase):
    def test_parse_response(self) -> None:
        raw = {"tipo_id": "A.B.C", "confianza": 0.9, "razonamiento": "ok"}
        resp = parse_l3_response(raw)
        self.assertEqual(resp.tipo_id, "A.B.C")
        self.assertAlmostEqual(resp.confianza, 0.9)

    def test_extract_json_markdown(self) -> None:
        text = '```json\n{"tipo_id": null, "confianza": 0.1}\n```'
        data = _extract_json(text)
        self.assertIsNone(data["tipo_id"])


class TestL3Classifier(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)

    def test_classify_with_mock(self) -> None:
        tipos = self.tax.tipos_para("ENERGIA", "ALUMBRADO PUBLICO")
        self.assertTrue(tipos)
        client = MockLLMClient()
        clf = ClassifierL3(self.tax, client, L3Config(min_confidence=0.75, mock=True))
        result, razon = clf.classify_row(
            sector="ENERGIA",
            subsector="ALUMBRADO PUBLICO",
            nombre="Mejoramiento alumbrado público sector centro",
            l1_tipo_id=tipos[0].tipo_id,
            l1_tipo_nombre=tipos[0].nombre,
            l1_estado="ambiguo",
        )
        self.assertIn(result.estado, (EstadoClasificacion.ASIGNADO, EstadoClasificacion.AMBIGUO))
        self.assertTrue(razon)

    def test_prompt_includes_tipos(self) -> None:
        tipos = self.tax.tipos_para("SALUD", "ALTA COMPLEJIDAD")
        self.assertGreaterEqual(len(tipos), 2)
        prompt = build_l3_user_prompt(
            sector="SALUD",
            subsector="ALTA COMPLEJIDAD",
            proyecto_text="Proyecto de prueba",
            tipos=tipos[:2],
        )
        data = json.loads(prompt)
        self.assertEqual(len(data["tipos_validos"]), 2)
        self.assertIn("tipo_id", data["tipos_validos"][0])

    def test_low_confidence_not_assigned(self) -> None:
        tipos = self.tax.tipos_para("ENERGIA", "ALUMBRADO PUBLICO")
        client = MagicMock()
        client.complete_json.return_value = {
            "tipo_id": tipos[0].tipo_id,
            "confianza": 0.4,
            "razonamiento": "poco claro",
        }
        clf = ClassifierL3(self.tax, client, L3Config(min_confidence=0.75))
        result, _ = clf.classify_row(
            sector="ENERGIA",
            subsector="ALUMBRADO PUBLICO",
            nombre="Proyecto genérico",
        )
        self.assertNotEqual(result.estado, EstadoClasificacion.ASIGNADO)


    def test_invalid_response_validation(self) -> None:
        resp = parse_l3_response({"tipo_id": "X", "confianza": "no-numero"})
        self.assertIsNone(resp.tipo_id)
        self.assertEqual(resp.confianza, 0.0)
        self.assertIsNotNone(resp.validation_error)

    def test_load_prompt_yaml(self) -> None:
        from proyecttype.paths import DEFAULT_L3_PROMPTS
        from proyecttype.prompts import load_l3_prompt_config

        cfg = load_l3_prompt_config(DEFAULT_L3_PROMPTS)
        self.assertGreaterEqual(cfg.version, 2)
        self.assertGreater(len(cfg.system_prompt), 50)
        self.assertGreaterEqual(len(cfg.edge_cases), 3)
        self.assertGreaterEqual(len(cfg.reasoning_steps), 3)
        self.assertIn("max_few_shot_examples", cfg.settings)

    def test_cot_response_parsing(self) -> None:
        raw = {
            "analisis": "Obra vial",
            "evidencia": ["conexión vial", "eje estructurante"],
            "candidatos_descartados": [{"tipo_id": "X.Y.Z", "motivo": "no aplica"}],
            "tipo_id": "A.B.C",
            "confianza": 0.9,
            "razonamiento": "Es vialidad estructurante",
        }
        resp = parse_l3_response(raw)
        self.assertEqual(resp.tipo_id, "A.B.C")
        self.assertIn("Análisis:", resp.razonamiento)
        self.assertIn("Evidencia:", resp.razonamiento)

    def test_user_prompt_includes_dynamic_context(self) -> None:
        tipos = self.tax.tipos_para("TRANSPORTE", "TRANSPORTE URBANO,VIALIDAD PEATONAL")
        if not tipos:
            self.skipTest("subsector transporte no disponible")
        prompt = build_l3_user_prompt(
            sector="TRANSPORTE",
            subsector="TRANSPORTE URBANO, Y VIALIDAD PEATONAL",
            proyecto_text="Obra vial de conexión",
            tipos=tipos,
        )
        data = json.loads(prompt)
        ctx = data.get("contexto_adicional") or {}
        self.assertIn("instruccion", data)
        # transporte urbano tiene pares confusos en colisiones_keyword
        self.assertTrue(ctx.get("pares_confusos") or ctx.get("ejemplos_referencia"))


class TestPromptFormat(unittest.TestCase):
    def test_format_tipo_truncates(self) -> None:
        from proyecttype.taxonomy import TipoProyecto

        tipo = TipoProyecto(
            tipo_id="X.Y.Z",
            nombre="TEST",
            definicion="A" * 500,
            sector="S",
            subsector="SS",
        )
        opt = format_tipo_option(tipo, max_def_chars=100)
        self.assertLessEqual(len(opt["definicion"]), 100)


class TestOllamaClient(unittest.TestCase):
    def test_ollama_complete_json(self) -> None:
        from unittest.mock import patch

        from proyecttype.llm_client import LLMConfig

        payload = {
            "message": {
                "content": json.dumps(
                    {
                        "tipo_id": "A.B.C",
                        "confianza": 0.9,
                        "razonamiento": "test ollama",
                    }
                )
            }
        }

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *args):
                return False

            def read(self):
                return json.dumps(payload).encode("utf-8")

        client = OllamaClient(LLMConfig(provider="ollama", model="llama3.2"))
        with patch("urllib.request.urlopen", return_value=FakeResponse()):
            data = client.complete_json(system="sys", user="user")
        self.assertEqual(data["tipo_id"], "A.B.C")
        self.assertAlmostEqual(data["confianza"], 0.9)


if __name__ == "__main__":
    unittest.main()
