"""Tipos compuestos: parsing de componentes e índice por subsector."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from projecttype.scorer import ProyectoTexto, ScorerConfig

import re
from dataclasses import dataclass

from .taxonomy import TipoProyecto
from .text_utils import contains_component, normalize_tipo_name


@dataclass(frozen=True)
class TipoComponents:
    """Partes de un tipo que deben evidenciarse en el texto del proyecto."""

    and_parts: tuple[str, ...]
    or_groups: tuple[tuple[str, ...], ...] = ()

    @property
    def is_composite(self) -> bool:
        return len(self.and_parts) > 1 or bool(self.or_groups)


@dataclass(frozen=True)
class CompositeRelation:
    composite: TipoProyecto
    components: TipoComponents
    subsets: tuple[TipoProyecto, ...]


@dataclass(frozen=True)
class CompositeAdjustment:
    tipo_id: str
    delta: int
    keyword: str
    campo: str


def _split_and_segments(name: str) -> list[str]:
    parts = [name]
    for pattern in (r"\s+y\s+", r"\s+mas\s+"):
        expanded: list[str] = []
        for part in parts:
            expanded.extend(p.strip() for p in re.split(pattern, part) if p.strip())
        parts = expanded
    return parts


def _extract_or_groups(name: str) -> tuple[str, tuple[tuple[str, ...], ...]]:
    or_groups: list[tuple[str, ...]] = []
    match = re.search(r"(.+?)\s+y/o\s+(.+)", name, flags=re.IGNORECASE)
    if match:
        left, right = match.group(1).strip(), match.group(2).strip()
        if " mas " in left:
            base, option_a = left.rsplit(" mas ", 1)
            or_groups.append((option_a.strip(), right))
            return base.strip(), tuple(or_groups)
        or_groups.append((left, right))
        return "", tuple(or_groups)
    return name, tuple(or_groups)


def _is_hierarchical_slash(name: str, sibling_names: frozenset[str]) -> bool:
    if "/" not in name:
        return False
    segments = [segment.strip() for segment in name.split("/") if segment.strip()]
    if len(segments) < 2:
        return False

    cumulative: list[str] = []
    paths: list[str] = []
    for index, segment in enumerate(segments):
        cumulative.append(segment if index == 0 else f"{cumulative[-1]}/{segment}")
        paths.append(normalize_tipo_name(cumulative[-1]))

    matches = sum(1 for path in paths if path in sibling_names)
    return matches >= 2


def parse_tipo_components(nombre: str, sibling_names: frozenset[str]) -> TipoComponents:
    """Descompone un nombre de tipo en componentes conjuntivos y grupos disyuntivos."""
    name = normalize_tipo_name(nombre)
    if not name:
        return TipoComponents(())

    name, or_groups = _extract_or_groups(name)
    and_parts: list[str] = []

    if name:
        if "/" in name and _is_hierarchical_slash(name, sibling_names):
            and_parts = [segment.strip() for segment in name.split("/") if segment.strip()]
        elif "/" in name:
            and_parts = [name]
        else:
            and_parts = _split_and_segments(name)

    and_tuple = tuple(part for part in and_parts if len(part) > 2)
    return TipoComponents(and_tuple, or_groups)


def components_match_text(components: TipoComponents, text: str) -> bool:
    if not components.is_composite:
        return False
    if components.and_parts and not all(
        contains_component(text, part) for part in components.and_parts
    ):
        return False
    for group in components.or_groups:
        if not any(contains_component(text, option) for option in group):
            return False
    return True


def _find_subset_tipos(
    composite: TipoProyecto,
    components: TipoComponents,
    tipos: list[TipoProyecto],
    parsed: dict[str, TipoComponents],
) -> tuple[TipoProyecto, ...]:
    subsets: list[TipoProyecto] = []
    composite_norm = composite.nombre_norm

    for tipo in tipos:
        if tipo.tipo_id == composite.tipo_id:
            continue
        other = parsed[tipo.tipo_id]
        if other.is_composite and len(other.and_parts) >= len(components.and_parts):
            continue

        if tipo.nombre_norm in components.and_parts:
            subsets.append(tipo)
            continue

        if (
            len(other.and_parts) == 1
            and other.and_parts[0] in components.and_parts
            and tipo.nombre_norm != composite_norm
        ):
            subsets.append(tipo)
            continue

        if tipo.nombre_norm in composite_norm and len(composite_norm) - len(tipo.nombre_norm) > 3:
            subsets.append(tipo)

    return tuple(subsets)


class CompositeIndex:
    """Relaciones compuesto ↔ subtipos, derivadas automáticamente de la taxonomía."""

    def __init__(self, relations: tuple[CompositeRelation, ...]) -> None:
        self.relations = relations

    @classmethod
    def from_tipos(cls, tipos: list[TipoProyecto]) -> CompositeIndex:
        sibling_names = frozenset(normalize_tipo_name(t.nombre) for t in tipos)
        parsed = {t.tipo_id: parse_tipo_components(t.nombre, sibling_names) for t in tipos}

        relations: list[CompositeRelation] = []
        for tipo in tipos:
            components = parsed[tipo.tipo_id]
            if not components.is_composite:
                continue
            subsets = _find_subset_tipos(tipo, components, tipos, parsed)
            relations.append(CompositeRelation(tipo, components, subsets))

        return cls(tuple(relations))

    def compute_adjustments(self, proyecto: ProyectoTexto, config: ScorerConfig) -> list[CompositeAdjustment]:
        all_text = proyecto.all_norm
        adjustments: list[CompositeAdjustment] = []
        penalize: set[str] = set()

        for relation in self.relations:
            if not components_match_text(relation.components, all_text):
                continue

            adjustments.append(
                CompositeAdjustment(
                    relation.composite.tipo_id,
                    config.composite_components_bonus,
                    "componentes_completos",
                    "tipo_compuesto",
                )
            )
            penalize.update(t.tipo_id for t in relation.subsets)

        for tipo_id in penalize:
            adjustments.append(
                CompositeAdjustment(
                    tipo_id,
                    config.composite_subset_penalty,
                    "subset_de_compuesto",
                    "subset_de_compuesto",
                )
            )

        return adjustments
