"""PT-4/PT-25: adaptador SniCommonsLLMClient sobre sni_commons.llm.

Verifica que complete_json() delega en structured_output() de un LLMProvider
de sni-commons (schema L3ResponseModel forzado por el backend, no texto libre
parseado con regex — PT-25), y que create_llm_client enruta a este adaptador
para los providers soportados.
"""

import unittest

from sni_commons.llm import EchoProvider, LLMResponseError, Message, StructuredResponse
from sni_commons.llm.protocol import Usage

from projecttype.l3_schema import L3ResponseModel
from projecttype.llm_client import (
    LLMConfig,
    MockLLMClient,
    SniCommonsLLMClient,
    create_llm_client,
)


class _StubProvider:
    """LLMProvider mínimo: devuelve una instancia fija como structured_output."""

    name = "stub"
    model = "stub-1"

    def __init__(self, instance: L3ResponseModel | None = None, *, error: Exception | None = None) -> None:
        self._instance = instance
        self._error = error

    async def chat(self, messages, **_kw):  # type: ignore[no-untyped-def] # pragma: no cover
        raise NotImplementedError

    async def structured_output(
        self, messages: list[Message], schema: type, **_kw
    ) -> StructuredResponse:
        if self._error:
            raise self._error
        assert self._instance is not None
        return StructuredResponse(
            data=self._instance,
            raw_text=self._instance.model_dump_json(),
            usage=Usage(),
            model=self.model,
        )

    async def embed(self, *a, **k):  # pragma: no cover
        raise NotImplementedError


class TestSniCommonsClient(unittest.TestCase):
    def _client_with(self, instance: L3ResponseModel) -> SniCommonsLLMClient:
        client = SniCommonsLLMClient.__new__(SniCommonsLLMClient)
        client._provider = _StubProvider(instance)  # type: ignore[attr-defined]
        return client

    def test_complete_json_returns_validated_dict(self) -> None:
        client = self._client_with(L3ResponseModel(tipo_id="X.1", confianza=0.9))
        out = client.complete_json(system="s", user="u")
        self.assertEqual(out["tipo_id"], "X.1")
        self.assertEqual(out["confianza"], 0.9)

    def test_complete_json_propagates_schema_mismatch(self) -> None:
        # Un mismatch de schema lo valida el backend (Vertex/Gemini) y llega
        # como LLMResponseError, reintentable — no un JSONParseError silencioso.
        client = SniCommonsLLMClient.__new__(SniCommonsLLMClient)
        client._provider = _StubProvider(  # type: ignore[attr-defined]
            error=LLMResponseError("schema mismatch")
        )
        with self.assertRaises(LLMResponseError):
            client.complete_json(system="s", user="u")

    def test_echo_provider_roundtrip(self) -> None:
        # Con EchoProvider real (sin red): structured_factory arma la instancia.
        client = SniCommonsLLMClient.__new__(SniCommonsLLMClient)
        client._provider = EchoProvider(  # type: ignore[attr-defined]
            structured_factory=lambda _messages, schema: schema(tipo_id="Z.3", confianza=1.0)
        )
        out = client.complete_json(system="ignored", user="ignored")
        self.assertEqual(out["tipo_id"], "Z.3")

    def test_create_llm_client_routes_to_adapter(self) -> None:
        for provider in ("gemini", "google", "openai", "ollama"):
            cfg = LLMConfig(provider=provider, model="m")  # type: ignore[arg-type]
            client = create_llm_client(cfg)
            self.assertIsInstance(client, SniCommonsLLMClient)

    def test_mock_unaffected(self) -> None:
        self.assertIsInstance(create_llm_client(mock=True), MockLLMClient)


if __name__ == "__main__":
    unittest.main()
