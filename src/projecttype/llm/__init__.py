"""Transporte LLM unificado (preset OBSRATE → sni-commons)."""

from projecttype.llm.provider import (
    DEFAULT_L3_MODEL,
    DEFAULT_LLM_PROVIDER,
    PROVIDER_ALIASES,
    build_provider,
    check_provider_available,
    describe_provider,
)

__all__ = [
    "DEFAULT_L3_MODEL",
    "DEFAULT_LLM_PROVIDER",
    "PROVIDER_ALIASES",
    "build_provider",
    "check_provider_available",
    "default_l3_concurrency",
    "describe_provider",
]
