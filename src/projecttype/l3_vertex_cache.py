"""Vertex Context Caching por subsector para L3 (ahorro de tokens de entrada).

Flujo recomendado: agrupar filas por ``(sector, subsector)``, crear una caché
con system + tipos_validos + contexto_adicional, clasificar todo el grupo con
``cached_content``, borrar la caché y pasar al siguiente subsector.
"""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any

from sni_commons.llm import CachedContext, VertexProvider

from .inference_metadata import prompt_version, taxonomy_hash
from .l3_schema import L3PromptConfig
from .prompts import build_l3_static_payload, get_l3_system_prompt
from .taxonomy import Taxonomia, TipoProyecto


def _slug(text: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", (text or "").strip().lower()).strip("-")
    return value[:48] or "na"


@dataclass
class SubsectorContextCache:
    """Caché Vertex activa para un subsector (una a la vez en el pipeline)."""

    sector: str
    subsector: str
    cache: CachedContext
    vertex: VertexProvider
    created: bool = True
    _deleted: bool = field(default=False, repr=False)

    @property
    def name(self) -> str:
        return self.cache.name

    def close(self) -> None:
        if self._deleted or not self.created:
            return
        try:
            asyncio.run(self.vertex.delete_context_cache(self.cache.name))
        except Exception:  # noqa: BLE001 — no abortar el lote por fallo de cleanup
            pass
        self._deleted = True


def build_subsector_cache_contents(
    *,
    sector: str,
    subsector: str,
    tipos: list[TipoProyecto],
    prompt_config: L3PromptConfig,
    max_def_chars: int = 400,
) -> tuple[str, str]:
    """Devuelve ``(system_instruction, static_contents_json)`` para ``create_context_cache``."""
    system = get_l3_system_prompt(prompt_config)
    static = build_l3_static_payload(
        sector=sector,
        subsector=subsector,
        tipos=tipos,
        max_def_chars=max_def_chars,
        prompt_config=prompt_config,
        include_dynamic_context=True,
    )
    return system, json.dumps(static, ensure_ascii=False, indent=2)


def create_subsector_cache(
    vertex: VertexProvider,
    *,
    sector: str,
    subsector: str,
    taxonomia: Taxonomia,
    prompt_config: L3PromptConfig,
    max_def_chars: int = 400,
    model: str | None = None,
    ttl_seconds: int | None = None,
) -> SubsectorContextCache:
    """Crea una CachedContent en Vertex para el subsector dado."""
    tipos = taxonomia.tipos_para(sector, subsector)
    system, contents = build_subsector_cache_contents(
        sector=sector,
        subsector=subsector,
        tipos=tipos,
        prompt_config=prompt_config,
        max_def_chars=max_def_chars,
    )
    ttl = ttl_seconds if ttl_seconds is not None else prompt_config.vertex_cache_ttl_seconds
    display = (
        f"pt-l3-{_slug(sector)}-{_slug(subsector)}"
        f"-{prompt_version()}-{taxonomy_hash()}"
    )[:128]
    cache = asyncio.run(
        vertex.create_context_cache(
            system_instruction=system,
            contents=contents,
            model=model,
            display_name=display,
            ttl_seconds=ttl,
        )
    )
    return SubsectorContextCache(
        sector=sector,
        subsector=subsector,
        cache=cache,
        vertex=vertex,
    )


def unwrap_vertex_provider(provider: Any) -> VertexProvider | None:
    """Extrae ``VertexProvider`` desde un ``RetryProvider`` o el propio Vertex."""
    if isinstance(provider, VertexProvider):
        return provider
    primary = getattr(provider, "primary", None)
    if isinstance(primary, VertexProvider):
        return primary
    return None
