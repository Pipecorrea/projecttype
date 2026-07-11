"""PT-25: `projecttype verify-llm` — smoke del proveedor configurado."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from sni_commons.llm import (
    ChatResponse,
    EchoProvider,
    LLMResponseError,
    Message,
    StructuredResponse,
)
from typer.testing import CliRunner

from projecttype.cli import app


class _FailingChatProvider:
    name = "stub"
    model = "stub-1"

    async def chat(self, *a: object, **k: object) -> ChatResponse:
        raise LLMResponseError("credenciales inválidas")

    async def structured_output(self, *a: object, **k: object) -> StructuredResponse:  # pragma: no cover
        raise NotImplementedError

    async def embed(self, *a: object, **k: object):  # pragma: no cover
        raise NotImplementedError


class _FailingStructuredProvider:
    name = "stub"
    model = "stub-1"

    async def chat(self, messages: list[Message], **_k: object) -> ChatResponse:
        return ChatResponse(text="OK", model=self.model)

    async def structured_output(self, *a: object, **k: object) -> StructuredResponse:
        raise LLMResponseError("schema mismatch")

    async def embed(self, *a: object, **k: object):  # pragma: no cover
        raise NotImplementedError


class TestVerifyLLM(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = CliRunner()

    def test_success_path(self) -> None:
        provider = EchoProvider(
            structured_factory=lambda _m, schema: schema(tipo_id=None, confianza=0.0)
        )
        with (
            patch("projecttype.llm.provider.check_provider_available"),
            patch("projecttype.llm.provider.build_provider", return_value=provider),
        ):
            result = self.runner.invoke(app, ["verify-llm"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("OK — el proveedor está listo", result.output)

    def test_missing_credentials_fails_fast(self) -> None:
        with patch(
            "projecttype.llm.provider.check_provider_available",
            side_effect=RuntimeError("GOOGLE_CLOUD_PROJECT requerido"),
        ):
            result = self.runner.invoke(app, ["verify-llm"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("GOOGLE_CLOUD_PROJECT", result.output)

    def test_chat_failure_reported(self) -> None:
        with (
            patch("projecttype.llm.provider.check_provider_available"),
            patch("projecttype.llm.provider.build_provider", return_value=_FailingChatProvider()),
        ):
            result = self.runner.invoke(app, ["verify-llm"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Falló la llamada simple", result.output)

    def test_structured_output_failure_reported(self) -> None:
        with (
            patch("projecttype.llm.provider.check_provider_available"),
            patch(
                "projecttype.llm.provider.build_provider",
                return_value=_FailingStructuredProvider(),
            ),
        ):
            result = self.runner.invoke(app, ["verify-llm"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Falló la llamada estructurada", result.output)


if __name__ == "__main__":
    unittest.main()
