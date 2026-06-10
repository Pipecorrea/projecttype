"""Carga e indexación de la taxonomía de tipos de proyecto."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from proyecttype.composite import CompositeIndex

import yaml

from .aliases import resolve_sector_subsector
from .text_utils import normalize_key, normalize_text, normalize_tipo_name


@dataclass(frozen=True)
class TipoProyecto:
    tipo_id: str
    nombre: str
    definicion: str
    sector: str
    subsector: str
    keywords_fuertes: tuple[str, ...] = ()
    keywords_debiles: tuple[str, ...] = ()
    excluye_si_contiene: tuple[str, ...] = ()
    keywords_fuertes_norm: tuple[str, ...] = field(init=False, repr=False)
    keywords_debiles_norm: tuple[str, ...] = field(init=False, repr=False)
    excluye_norm: tuple[str, ...] = field(init=False, repr=False)
    nombre_norm: str = field(init=False, repr=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "keywords_fuertes_norm", _norm_keywords(self.keywords_fuertes))
        object.__setattr__(self, "keywords_debiles_norm", _norm_keywords(self.keywords_debiles))
        object.__setattr__(self, "excluye_norm", _norm_keywords(self.excluye_si_contiene))
        object.__setattr__(self, "nombre_norm", normalize_tipo_name(self.nombre))


def _coerce_keywords(raw: list[Any] | tuple[Any, ...] | None) -> tuple[str, ...]:
    if not raw:
        return ()
    return tuple(str(kw) for kw in raw if kw is not None and str(kw).strip())


def _norm_keywords(keywords: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for kw in keywords:
        norm = normalize_text(kw)
        if norm and norm not in seen:
            seen.add(norm)
            result.append(norm)
    return tuple(result)


def _parse_tipo(raw: dict[str, Any], sector: str, subsector: str) -> TipoProyecto:
    return TipoProyecto(
        tipo_id=raw["tipo_id"],
        nombre=raw["nombre"],
        definicion=raw.get("definicion", ""),
        sector=sector,
        subsector=subsector,
        keywords_fuertes=_coerce_keywords(raw.get("keywords_fuertes")),
        keywords_debiles=_coerce_keywords(raw.get("keywords_debiles")),
        excluye_si_contiene=_coerce_keywords(raw.get("excluye_si_contiene")),
    )


class Taxonomia:
    """Taxonomía indexada por (sector, subsector) normalizados."""

    def __init__(self, tipos: list[TipoProyecto]) -> None:
        self.tipos = tipos
        self._by_sector_subsector: dict[tuple[str, str], list[TipoProyecto]] = {}
        self._composite_index: dict[tuple[str, str], Any] = {}
        for tipo in tipos:
            key = (normalize_key(tipo.sector), normalize_key(tipo.subsector))
            self._by_sector_subsector.setdefault(key, []).append(tipo)

    @classmethod
    def from_yaml(cls, path: str | Path) -> Taxonomia:
        path = Path(path)
        with path.open(encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        tipos: list[TipoProyecto] = []
        for sector_block in data.get("sectores", []):
            sector = sector_block["sector"]
            for sub_block in sector_block.get("subsectores", []):
                subsector = sub_block["subsector"]
                for raw_tipo in sub_block.get("tipos", []):
                    tipos.append(_parse_tipo(raw_tipo, sector, subsector))
        return cls(tipos)

    def tipos_para(self, sector: str | None, subsector: str | None) -> list[TipoProyecto]:
        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        return list(self._by_sector_subsector.get((sector_res, subsector_res), ()))

    def composite_index_para(self, sector: str | None, subsector: str | None) -> CompositeIndex:
        from .composite import CompositeIndex

        sector_res, subsector_res = resolve_sector_subsector(sector, subsector)
        key = (sector_res, subsector_res)
        if key not in self._composite_index:
            tipos = self._by_sector_subsector.get(key, [])
            self._composite_index[key] = CompositeIndex.from_tipos(tipos)
        index: CompositeIndex = self._composite_index[key]
        return index

    def tiene_subsector(self, sector: str | None, subsector: str | None) -> bool:
        return bool(self.tipos_para(sector, subsector))

    @property
    def n_tipos(self) -> int:
        return len(self.tipos)

    @property
    def n_subsectores(self) -> int:
        return len(self._by_sector_subsector)
