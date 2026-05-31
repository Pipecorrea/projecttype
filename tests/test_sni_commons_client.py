"""PT-4: adaptador SniCommonsLLMClient sobre sni_commons.llm.

Verifica que complete_json() delega en un LLMProvider de sni-commons, parsea el
JSON (incluyendo fenced ```json```), y que create_llm_client enruta a este
adaptador para los providers soportados.
"""

import unittest

from sni_commons.llm import ChatResponse, EchoProvider

from proyecttype.llm_client import (
    LLMConfig,
    MockLLMClient,
    SniCommonsLLMClient,
    create_llm_client,
)


class _StubProvider:
    """LLMProvider mínimo: devuelve un texto fijo como respuesta de chat."""

    name = "stub"
    model = "stub-1"

    def __init__(self, text: str) -> None:
        self._text = text

    async def chat(self, messages, **_kw) -> ChatResponse:  # type: ignore[no-untyped-def]
        return ChatResponse(text=self._text, model=self.model)

    async def structured_output(self, *a, **k):  # pragma: no cover
        raise NotImplementedError

    async def embed(self, *a, **k):  # pragma: no cover
        raise NotImplementedError


class TestSniCommonsClient(unittest.TestCase):
    def _client_with(self, text: str) -> SniCommonsLLMClient:
        client = SniCommonsLLMClient.__new__(SniCommonsLLMClient)
        client._provider = _StubProvider(text)  # type: ignore[attr-defined]
        return client

    def test_complete_json_parses_plain_json(self) -> None:
        client = self._client_with('{"tipo_id": "X.1", "confianza": 0.9}')
        out = client.complete_json(system="s", user="u")
        self.assertEqual(out["tipo_id"], "X.1")
        self.assertEqual(out["confianza"], 0.9)

    def test_complete_json_parses_fenced_json(self) -> None:
        client = self._client_with('```json\n{"tipo_id": "Y.2", "confianza": 0.5}\n```')
        out = client.complete_json(system="s", user="u")
        self.assertEqual(out["tipo_id"], "Y.2")

    def test_echo_provider_roundtrip(self) -> None:
        # Con EchoProvider real (sin red): el user es un JSON, echo lo devuelve.
        client = SniCommonsLLMClient.__new__(SniCommonsLLMClient)
        client._provider = EchoProvider()  # type: ignore[attr-defined]
        out = client.complete_json(system="ignored", user='{"tipo_id": "Z.3", "confianza": 1.0}')
        self.assertEqual(out["tipo_id"], "Z.3")

    def test_create_llm_client_routes_to_adapter(self) -> None:
        # provider google/openai/ollama -> adaptador sni-commons (no instancia red).
        for provider in ("google", "openai", "ollama"):
            cfg = LLMConfig(provider=provider, model="m")
            client = create_llm_client(cfg)
            self.assertIsInstance(client, SniCommonsLLMClient)

    def test_create_llm_client_legacy_fallback(self) -> None:
        cfg = LLMConfig(provider="ollama", model="m")
        client = create_llm_client(cfg, use_sni_commons=False)
        self.assertNotIsInstance(client, SniCommonsLLMClient)

    def test_mock_unaffected(self) -> None:
        self.assertIsInstance(create_llm_client(mock=True), MockLLMClient)


if __name__ == "__main__":
    unittest.main()
