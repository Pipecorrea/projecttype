"""Tests del mapa de proveedores LLM (Vertex como OBSRATE)."""

from __future__ import annotations

import unittest

from projecttype.llm.provider import (
    DEFAULT_L3_CONCURRENCY,
    PROVIDER_ALIASES,
    default_l3_concurrency,
    default_llm_provider,
)


class TestLlmProvider(unittest.TestCase):
    def test_gemini_maps_to_vertex(self) -> None:
        self.assertEqual(PROVIDER_ALIASES["gemini"], "vertex")

    def test_google_maps_to_ai_studio(self) -> None:
        self.assertEqual(PROVIDER_ALIASES["google"], "gemini")
        self.assertEqual(PROVIDER_ALIASES["gemini-studio"], "gemini")

    def test_default_provider_is_gemini(self) -> None:
        self.assertEqual(default_llm_provider(), "gemini")

    def test_default_concurrency_matches_obsrate(self) -> None:
        self.assertEqual(default_l3_concurrency(), DEFAULT_L3_CONCURRENCY)


if __name__ == "__main__":
    unittest.main()
