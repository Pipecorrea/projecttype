"""Caché persistente de resultados L3 por código BIP."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .scorer import EstadoClasificacion, ResultadoClasificacion

L3_CACHE_VERSION = "1"


@dataclass
class L3CacheEntry:
    codigo_bip: str
    model: str
    l3_estado: str
    l3_tipo_id: str | None
    l3_tipo_nombre: str | None
    l3_confianza: float | None
    l3_razonamiento: str | None
    cache_version: str = L3_CACHE_VERSION
    cached_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "codigo_bip": self.codigo_bip,
            "model": self.model,
            "cache_version": self.cache_version,
            "cached_at": self.cached_at,
            "l3_estado": self.l3_estado,
            "l3_tipo_id": self.l3_tipo_id,
            "l3_tipo_nombre": self.l3_tipo_nombre,
            "l3_confianza": self.l3_confianza,
            "l3_razonamiento": self.l3_razonamiento,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> L3CacheEntry:
        return cls(
            codigo_bip=str(data["codigo_bip"]),
            model=str(data.get("model") or ""),
            cache_version=str(data.get("cache_version") or ""),
            cached_at=str(data.get("cached_at") or ""),
            l3_estado=str(data.get("l3_estado") or "sin_match"),
            l3_tipo_id=data.get("l3_tipo_id"),
            l3_tipo_nombre=data.get("l3_tipo_nombre"),
            l3_confianza=data.get("l3_confianza"),
            l3_razonamiento=data.get("l3_razonamiento"),
        )


class L3ResultCache:
    def __init__(self, path: Path, *, model: str) -> None:
        self.path = path
        self.model = model
        self._entries: dict[str, L3CacheEntry] = {}
        self.hits = 0
        self.api_calls = 0
        self._load()

    def _load(self) -> None:
        if not self.path.is_file():
            return
        with self.path.open(encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = L3CacheEntry.from_dict(json.loads(line))
                except (json.JSONDecodeError, KeyError):
                    continue
                self._entries[entry.codigo_bip] = entry

    def get(self, codigo_bip: str) -> L3CacheEntry | None:
        entry = self._entries.get(codigo_bip)
        if entry is None:
            return None
        if entry.cache_version != L3_CACHE_VERSION or entry.model != self.model:
            return None
        self.hits += 1
        return entry

    def put(
        self,
        codigo_bip: str,
        result: ResultadoClasificacion,
        razonamiento: str,
    ) -> None:
        entry = L3CacheEntry(
            codigo_bip=codigo_bip,
            model=self.model,
            cache_version=L3_CACHE_VERSION,
            cached_at=datetime.now(UTC).isoformat(),
            l3_estado=result.estado.value,
            l3_tipo_id=result.tipo_id,
            l3_tipo_nombre=result.tipo_nombre,
            l3_confianza=result.score,
            l3_razonamiento=razonamiento or None,
        )
        self._entries[codigo_bip] = entry

    def save(self) -> None:
        """Reescribe el archivo consolidado (sin duplicados)."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as fh:
            for entry in self._entries.values():
                fh.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")

    @property
    def size(self) -> int:
        return len(self._entries)


def entry_to_result(
    entry: L3CacheEntry,
    *,
    sector_res: str,
    subsector_res: str,
) -> tuple[ResultadoClasificacion, str]:
    result = ResultadoClasificacion(
        estado=EstadoClasificacion(entry.l3_estado),
        tipo_id=entry.l3_tipo_id,
        tipo_nombre=entry.l3_tipo_nombre,
        score=float(entry.l3_confianza or 0.0),
        nivel=3,
        sector_resuelto=sector_res,
        subsector_resuelto=subsector_res,
    )
    return result, entry.l3_razonamiento or ""
