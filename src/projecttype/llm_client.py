"""Clientes LLM para Nivel 3 (sni_commons.llm + mock de pruebas)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Literal, Protocol

LLMProvider = Literal["gemini", "gemini-studio", "google", "vertex", "anthropic", "openai", "ollama"]


class LLMClient(Protocol):
    def complete_json(
        self,
        *,
        system: str,
        user: str,
        cached_content: str | None = None,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider = "gemini"
    model: str = ""
    api_key_env: str = "OPENAI_API_KEY"
    base_url_env: str = "OPENAI_BASE_URL"
    ollama_base_url: str = "http://localhost:11434"
    ollama_base_url_env: str = "OLLAMA_BASE_URL"
    ollama_model_env: str = "OLLAMA_MODEL"
    google_api_key_env: str = "GEMINI_API_KEY"
    google_api_key_fallback_env: str = "GOOGLE_API_KEY"
    google_model_env: str = "GEMINI_MODEL"
    temperature: float = 0.0
    max_tokens: int = 2048
    timeout_seconds: float = 120.0
    request_interval_seconds: float = 0.0
    max_retries: int = 4

    def effective_request_interval(self) -> float:
        """Pausa entre llamadas; solo AI Studio free tier usa throttle por defecto."""
        if self.request_interval_seconds > 0:
            return self.request_interval_seconds
        from projecttype.llm.provider import PROVIDER_ALIASES

        kind = PROVIDER_ALIASES.get(self.provider, self.provider)
        if kind == "gemini":
            env = os.environ.get("GEMINI_REQUEST_INTERVAL")
            if env:
                return float(env)
            return 5.0
        return 0.0

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        from projecttype.llm.provider import default_llm_model

        if self.provider in ("gemini", "gemini-studio", "google", "vertex"):
            return default_llm_model()
        if self.provider == "ollama":
            return os.environ.get(self.ollama_model_env) or "llama3.2"
        return "gpt-4o-mini"

    def resolved_google_api_key(self) -> str:
        return (
            os.environ.get(self.google_api_key_env)
            or os.environ.get(self.google_api_key_fallback_env)
            or ""
        )

    def resolved_ollama_base_url(self) -> str:
        return os.environ.get(self.ollama_base_url_env) or self.ollama_base_url


def list_ollama_models(*, base_url: str | None = None, timeout_seconds: float = 10.0) -> list[str]:
    """Lista modelos disponibles en Ollama (`GET /api/tags`)."""
    root = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    request = urllib.request.Request(f"{root}/api/tags", method="GET")
    with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
        payload = json.loads(response.read().decode("utf-8"))
    models = payload.get("models") or []
    return [str(item.get("name", "")) for item in models if item.get("name")]


def check_ollama_available(*, base_url: str | None = None, model: str | None = None) -> None:
    root = (base_url or os.environ.get("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/")
    try:
        models = list_ollama_models(base_url=root)
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"No se pudo conectar a Ollama en {root}. "
            "¿Está corriendo? Prueba: ollama serve"
        ) from exc
    if not models:
        raise RuntimeError(f"Ollama en {root} no tiene modelos. Instala uno: ollama pull llama3.2")
    if model and model not in models and not any(model in name for name in models):
        available = ", ".join(models[:8])
        raise RuntimeError(
            f"Modelo Ollama '{model}' no encontrado. Disponibles: {available}"
        )


def check_gemini_available(*, api_key: str | None = None) -> None:
    key = api_key or LLMConfig(provider="google").resolved_google_api_key()
    if not key:
        raise RuntimeError(
            "Variable de entorno GEMINI_API_KEY (o GOOGLE_API_KEY) no definida."
        )


class SniCommonsLLMClient:
    """Adaptador del cliente unificado `sni_commons.llm` al Protocol L3."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        from projecttype.llm.provider import build_provider

        cfg = config or LLMConfig()
        self._provider = build_provider(
            cfg.provider,
            model=cfg.resolved_model(),
            request_interval_seconds=cfg.effective_request_interval(),
        )

    @property
    def provider(self) -> Any:
        return self._provider

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        cached_content: str | None = None,
    ) -> dict[str, Any]:
        """Llama L3 con salida estructurada (response_schema/tool-use nativo).

        Antes pedía texto libre (``chat``) y parseaba JSON con regex propia: un
        JSON truncado o con markdown fallaba silencioso, sin pasar por el
        proveedor. Con ``structured_output`` el backend fuerza el schema y
        valida con Pydantic; un mismatch llega como ``LLMResponseError``
        (mismo patrón que OBSRATE, PT-25).
        """
        import asyncio

        from sni_commons.llm import Message

        from .l3_schema import L3ResponseModel

        if cached_content:
            messages = [Message(role="user", content=user)]
            cache_kw: dict[str, Any] = {"cached_content": cached_content}
        else:
            messages = [
                Message(role="system", content=system),
                Message(role="user", content=user),
            ]
            cache_kw = {}
        resp = asyncio.run(
            self._provider.structured_output(messages, L3ResponseModel, **cache_kw)
        )
        return resp.data.model_dump(mode="json")


class MockLLMClient:
    """Cliente de prueba: elige el primer tipo_id válido mencionado en el prompt."""

    def __init__(self, fail_on_calls: frozenset[int] | None = None) -> None:
        self.fail_on_calls = fail_on_calls or frozenset()
        self.calls = 0
        self.last_cached_content: str | None = None

    def complete_json(
        self,
        *,
        system: str,
        user: str,
        cached_content: str | None = None,
    ) -> dict[str, Any]:
        del system
        self.last_cached_content = cached_content
        self.calls += 1
        if self.calls in self.fail_on_calls:
            from sni_commons.llm import LLMResponseError

            raise LLMResponseError(f"Mock 503 UNAVAILABLE en llamada {self.calls}")
        data = json.loads(user)
        # Con cache, el user solo trae proyecto; tipos vienen del system/cache mock.
        tipos = data.get("tipos_validos") or []
        sugerencias = data.get("sugerencias_previas") or {}
        l1 = sugerencias.get("l1_candidato") or ""
        if not l1 and isinstance(sugerencias.get("l1"), dict):
            l1 = str(sugerencias["l1"].get("candidato") or "")
        for tipo in tipos:
            tid = tipo.get("tipo_id", "")
            nombre = tipo.get("nombre", "")
            if tid and tid in l1:
                return {
                    "tipo_id": tid,
                    "confianza": 0.8,
                    "razonamiento": "Mock: coincide con candidato L1.",
                }
            if nombre and nombre in l1:
                return {
                    "tipo_id": tid,
                    "confianza": 0.8,
                    "razonamiento": "Mock: coincide con candidato L1.",
                }
        if tipos:
            return {
                "tipo_id": tipos[0]["tipo_id"],
                "confianza": 0.5,
                "razonamiento": "Mock: confianza insuficiente.",
            }
        # dynamic_only sin tipos en el user: devolver null (tests de cache)
        if cached_content and "proyecto" in data and "tipos_validos" not in data:
            return {
                "tipo_id": None,
                "confianza": 0.0,
                "razonamiento": "Mock: respuesta con cached_content (sin tipos en user).",
            }
        return {"tipo_id": None, "confianza": 0.0, "razonamiento": "Mock: sin tipos."}


def create_llm_client(
    config: LLMConfig | None = None,
    *,
    mock: bool = False,
) -> LLMClient:
    """Crea el cliente L3 vía ``sni_commons.llm`` (ADR-1) o mock de pruebas."""
    if mock:
        return MockLLMClient()
    return SniCommonsLLMClient(config or LLMConfig(provider="gemini"))
