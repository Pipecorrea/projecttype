"""Transporte LLM de ProjectType sobre ``sni_commons.llm`` (mismo mapa que OBSRATE).

================  ======================  =========================================
ProjectType       sni-commons             Qué es
================  ======================  =========================================
``gemini``        ``vertex``              Gemini en Vertex AI (ADC, project+region)
``gemini-studio`` ``gemini``              Gemini en Google AI Studio (GEMINI_API_KEY)
``google``        ``gemini``              Alias legacy de gemini-studio
``vertex``        ``anthropic_vertex``    Claude en Vertex AI
``anthropic``     ``anthropic``           Anthropic API directa
``openai``        ``openai``              OpenAI API
``ollama``        ``ollama``              Ollama local
================  ======================  =========================================
"""

from __future__ import annotations

import os

from sni_commons.llm import LLMConfig as ScLLMConfig
from sni_commons.llm import LLMProvider, make_provider

__all__ = [
    "DEFAULT_L3_CONCURRENCY",
    "DEFAULT_L3_MODEL",
    "DEFAULT_LLM_PROVIDER",
    "PROVIDER_ALIASES",
    "build_provider",
    "check_provider_available",
    "default_l3_concurrency",
    "describe_provider",
]

DEFAULT_LLM_PROVIDER = "gemini"
DEFAULT_L3_MODEL = "gemini-2.5-flash"
DEFAULT_L3_CONCURRENCY = 5

PROVIDER_ALIASES: dict[str, str] = {
    "gemini": "vertex",
    "gemini-studio": "gemini",
    "google": "gemini",
    "vertex": "anthropic_vertex",
    "anthropic": "anthropic",
    "openai": "openai",
    "ollama": "ollama",
}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def default_llm_provider() -> str:
    return _env("LLM_PROVIDER", DEFAULT_LLM_PROVIDER)


def default_llm_model() -> str:
    return _env("LLM_MODEL") or _env("GEMINI_MODEL", DEFAULT_L3_MODEL)


def default_l3_concurrency() -> int:
    raw = _env("LLM_MAX_CONCURRENCY", str(DEFAULT_L3_CONCURRENCY))
    try:
        return max(1, int(raw))
    except ValueError:
        return DEFAULT_L3_CONCURRENCY


def describe_provider(provider: str | None = None) -> str:
    """Etiqueta legible para logs (p. ej. ``Vertex AI / gemini-2.5-flash``)."""
    name = provider or default_llm_provider()
    kind = PROVIDER_ALIASES.get(name, name)
    model = default_llm_model()
    labels = {
        "vertex": "Vertex AI",
        "gemini": "Google AI Studio",
        "anthropic_vertex": "Claude en Vertex",
        "anthropic": "Anthropic API",
        "openai": "OpenAI",
        "ollama": "Ollama",
    }
    return f"{labels.get(kind, kind)} / {model}"


def check_provider_available(provider: str | None = None) -> None:
    """Valida credenciales mínimas antes de una corrida L3 real."""
    name = provider or default_llm_provider()
    kind = PROVIDER_ALIASES.get(name)
    if kind is None:
        raise RuntimeError(
            f"LLM provider desconocido: {name!r}. "
            f"Válidos: {', '.join(sorted(PROVIDER_ALIASES))}."
        )
    if kind in {"vertex", "anthropic_vertex"}:
        if not _env("GOOGLE_CLOUD_PROJECT"):
            raise RuntimeError(
                "GOOGLE_CLOUD_PROJECT requerido para Vertex. "
                "Autenticación: gcloud auth application-default login"
            )
    elif kind == "gemini":
        if not (_env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY")):
            raise RuntimeError(
                "GEMINI_API_KEY requerida para gemini-studio (Google AI Studio)."
            )
    elif kind == "anthropic":
        if not _env("ANTHROPIC_API_KEY"):
            raise RuntimeError("ANTHROPIC_API_KEY requerida para provider anthropic.")
    elif kind == "openai":
        if not _env("OPENAI_API_KEY"):
            raise RuntimeError("OPENAI_API_KEY requerida para provider openai.")


def build_provider(
    provider: str | None = None,
    *,
    model: str | None = None,
    request_interval_seconds: float | None = None,
) -> LLMProvider:
    """Construye el provider de sni-commons según alias de ProjectType/OBSRATE."""
    name = provider or default_llm_provider()
    kind = PROVIDER_ALIASES.get(name)
    if kind is None:
        raise ValueError(
            f"LLM provider desconocido: {name!r}. "
            f"Válidos: {', '.join(sorted(PROVIDER_ALIASES))}."
        )

    api_key = None
    if kind == "gemini":
        api_key = _env("GEMINI_API_KEY") or _env("GOOGLE_API_KEY") or None
    elif kind == "anthropic":
        api_key = _env("ANTHROPIC_API_KEY") or None
    elif kind == "openai":
        api_key = _env("OPENAI_API_KEY") or None

    interval = request_interval_seconds
    if interval is None:
        if kind == "gemini":
            raw = _env("GEMINI_REQUEST_INTERVAL", "5")
            interval = float(raw) if raw else 5.0
        else:
            interval = 0.0

    config = ScLLMConfig(
        provider=kind,
        model=model or default_llm_model(),
        api_key=api_key,
        project=_env("GOOGLE_CLOUD_PROJECT") or None,
        location=_env("GOOGLE_CLOUD_REGION", "us-east5") or None,
        max_retries=4,
        request_interval_seconds=interval,
    )
    return make_provider(config)
