"""Clientes LLM para Nivel 3 (OpenAI, Google Gemini, Ollama local, mock)."""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Literal, Protocol

LLMProvider = Literal["openai", "ollama", "google"]


class LLMClient(Protocol):
    def complete_json(self, *, system: str, user: str) -> dict: ...


@dataclass(frozen=True)
class LLMConfig:
    provider: LLMProvider = "ollama"
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
        """Pausa entre llamadas (Gemini free tier ~15 RPM → default 5 s)."""
        if self.request_interval_seconds > 0:
            return self.request_interval_seconds
        if self.provider == "google":
            env = os.environ.get("GEMINI_REQUEST_INTERVAL")
            if env:
                return float(env)
            return 5.0
        return 0.0

    def resolved_model(self) -> str:
        if self.model:
            return self.model
        if self.provider == "ollama":
            return os.environ.get(self.ollama_model_env) or "llama3.2"
        if self.provider == "google":
            return os.environ.get(self.google_model_env) or "gemini-2.5-flash"
        return "gpt-4o-mini"

    def resolved_google_api_key(self) -> str:
        return (
            os.environ.get(self.google_api_key_env)
            or os.environ.get(self.google_api_key_fallback_env)
            or ""
        )

    def resolved_ollama_base_url(self) -> str:
        return os.environ.get(self.ollama_base_url_env) or self.ollama_base_url


class JSONParseError(ValueError):
    """Respuesta LLM no parseable como JSON."""


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise JSONParseError(str(exc)) from exc


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


class GeminiClient:
    """Cliente Google AI Studio / Gemini API (REST, cuota gratuita con API key)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig(provider="google")
        self.api_key = self.config.resolved_google_api_key()
        if not self.api_key:
            raise RuntimeError(
                f"Variable de entorno {self.config.google_api_key_env} "
                f"(o {self.config.google_api_key_fallback_env}) no definida."
            )
        self.model = self.config.resolved_model()
        self._last_request_at = 0.0

    def _throttle(self) -> None:
        interval = self.config.effective_request_interval()
        if interval <= 0:
            return
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < interval:
            time.sleep(interval - elapsed)

    def _request(self, *, system: str, user: str, max_output_tokens: int) -> str:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model}:generateContent"
        )
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {
                "temperature": self.config.temperature,
                "maxOutputTokens": max_output_tokens,
                "responseMimeType": "application/json",
            },
        }
        data = json.dumps(body).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "x-goog-api-key": self.api_key,
        }
        last_error: RuntimeError | None = None
        for attempt in range(self.config.max_retries):
            self._throttle()
            request = urllib.request.Request(
                url,
                data=data,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                self._last_request_at = time.monotonic()
                break
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                last_error = RuntimeError(f"Gemini HTTP {exc.code}: {detail}")
                if exc.code == 429 and attempt < self.config.max_retries - 1:
                    time.sleep(min(60.0, 5.0 * (2**attempt)))
                    continue
                raise last_error from exc
            except urllib.error.URLError as exc:
                raise RuntimeError("No se pudo conectar a la API de Gemini.") from exc
        else:
            assert last_error is not None
            raise last_error

        candidates = payload.get("candidates") or []
        if not candidates:
            block = (payload.get("promptFeedback") or {}).get("blockReason")
            raise RuntimeError(f"Gemini sin candidatos en la respuesta. blockReason={block}")
        parts = (candidates[0].get("content") or {}).get("parts") or []
        if not parts:
            raise RuntimeError("Gemini devolvió contenido vacío.")
        return str(parts[0].get("text") or "{}")

    def complete_json(self, *, system: str, user: str) -> dict:
        max_tokens = self.config.max_tokens
        last_error: JSONParseError | None = None
        for attempt in range(3):
            content = self._request(
                system=system,
                user=user,
                max_output_tokens=min(max_tokens * (attempt + 1), 8192),
            )
            try:
                return _extract_json(content)
            except JSONParseError as exc:
                last_error = exc
        assert last_error is not None
        raise last_error


class OpenAIClient:
    """Cliente OpenAI / compatible (Azure, proxy OpenAI)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig(provider="openai")
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise RuntimeError(
                f"Variable de entorno {self.config.api_key_env} no definida."
            )
        from openai import OpenAI

        kwargs: dict = {"api_key": api_key}
        base_url = os.environ.get(self.config.base_url_env)
        if base_url:
            kwargs["base_url"] = base_url
        self._client = OpenAI(**kwargs)

    def complete_json(self, *, system: str, user: str) -> dict:
        response = self._client.chat.completions.create(
            model=self.config.resolved_model(),
            temperature=self.config.temperature,
            max_tokens=self.config.max_tokens,
            timeout=self.config.timeout_seconds,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content or "{}"
        return _extract_json(content)


class OllamaClient:
    """Cliente nativo Ollama (`POST /api/chat` con `format: json`)."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig(provider="ollama")
        self.base_url = self.config.resolved_ollama_base_url().rstrip("/")
        self.model = self.config.resolved_model()

    def complete_json(self, *, system: str, user: str) -> dict:
        body = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        data = json.dumps(body).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/api/chat",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Ollama HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(
                f"No se pudo conectar a Ollama en {self.base_url}. ¿Está corriendo?"
            ) from exc

        content = (payload.get("message") or {}).get("content") or "{}"
        last_error: JSONParseError | None = None
        for attempt in range(3):
            try:
                return _extract_json(content)
            except JSONParseError as exc:
                last_error = exc
                if attempt >= 2:
                    break
                body["options"]["num_predict"] = min(
                    self.config.max_tokens * (attempt + 2),
                    4096,
                )
                data = json.dumps(body).encode("utf-8")
                request = urllib.request.Request(
                    f"{self.base_url}/api/chat",
                    data=data,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                content = (payload.get("message") or {}).get("content") or "{}"
        assert last_error is not None
        raise last_error


class SniCommonsLLMClient:
    """Adaptador del cliente unificado `sni_commons.llm` al Protocol L3.

    Implementa `complete_json(system, user) -> dict` delegando en
    `sni_commons.llm` (ADR-1). El prompt L3 ya pide JSON explícitamente, así que
    se usa `chat()` (texto) + `_extract_json`, en vez de `structured_output`
    (que exigiría un esquema estricto e incompatible con el chain-of-thought de
    campos opcionales del L3).

    `provider` acepta los presets de sni-commons: gemini, openai, groq,
    openrouter, deepseek, together, ollama, echo. Reemplaza Gemini/OpenAI/Ollama
    propios sin perder cobertura (Vertex queda pendiente de un backend dedicado).
    """

    def __init__(self, config: LLMConfig | None = None) -> None:
        from sni_commons.llm import LLMConfig as _ScLLMConfig
        from sni_commons.llm import make_provider

        cfg = config or LLMConfig()
        provider = cfg.provider
        # 'google' es el nombre histórico de ProyectType para Gemini AI Studio.
        sc_provider = "gemini" if provider == "google" else provider
        api_key = ""
        if sc_provider == "gemini":
            api_key = cfg.resolved_google_api_key()
        elif sc_provider not in {"ollama", "echo"}:
            api_key = os.environ.get(cfg.api_key_env, "")
        self._provider = make_provider(
            _ScLLMConfig(
                provider=sc_provider,
                model=cfg.resolved_model(),
                api_key=api_key or None,
                timeout_seconds=cfg.timeout_seconds,
                max_retries=cfg.max_retries,
                request_interval_seconds=cfg.effective_request_interval(),
            )
        )

    def complete_json(self, *, system: str, user: str) -> dict:
        import asyncio

        from sni_commons.llm import Message

        messages = [
            Message(role="system", content=system),
            Message(role="user", content=user),
        ]
        resp = asyncio.run(self._provider.chat(messages))
        return _extract_json(resp.text)


class MockLLMClient:
    """Cliente de prueba: elige el primer tipo_id válido mencionado en el prompt."""

    def complete_json(self, *, system: str, user: str) -> dict:
        del system
        data = json.loads(user)
        tipos = data.get("tipos_validos") or []
        sugerencias = data.get("sugerencias_previas") or {}
        l1 = sugerencias.get("l1_candidato") or ""
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
        return {"tipo_id": None, "confianza": 0.0, "razonamiento": "Mock: sin tipos."}


# Providers que el cliente unificado sni-commons cubre de forma nativa.
_SNI_COMMONS_PROVIDERS = frozenset({"google", "openai", "ollama"})


def create_llm_client(
    config: LLMConfig | None = None,
    *,
    mock: bool = False,
    use_sni_commons: bool = True,
) -> LLMClient:
    """Crea el cliente L3.

    Por defecto usa el cliente unificado `sni_commons.llm` (ADR-1) para los
    providers que soporta (google→gemini, openai, ollama). Los clientes legacy
    (`GeminiClient`/`OpenAIClient`/`OllamaClient`) se conservan como fallback
    activable con ``use_sni_commons=False``.
    """
    if mock:
        return MockLLMClient()
    cfg = config or LLMConfig()
    if use_sni_commons and cfg.provider in _SNI_COMMONS_PROVIDERS:
        return SniCommonsLLMClient(cfg)
    if cfg.provider == "ollama":
        return OllamaClient(cfg)
    if cfg.provider == "google":
        return GeminiClient(cfg)
    return OpenAIClient(cfg)
