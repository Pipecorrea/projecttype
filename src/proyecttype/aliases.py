"""Mapeos explícitos BIP → taxonomía oficial."""

from __future__ import annotations

from .text_utils import normalize_key

# sector BIP normalizado -> sector taxonomía normalizado
SECTOR_ALIASES: dict[str, str] = {
    "DEPORTES": "DEPORTE",
    "EDUCACION": "EDUCACION",  # YAML usa EDUCACIÓN; normalize_key quita acentos
}

# (sector_bip, subsector_bip) normalizados -> (sector_tax, subsector_tax) normalizados
SUBSECTOR_ALIASES: dict[tuple[str, str], tuple[str, str]] = {
    ("DEPORTE", "DEPORTE RECREATIVO"): ("DEPORTE", "RECREATIVO"),
    ("DEPORTE", "DEPORTE FORMATIVO"): ("DEPORTE", "FORMATIVO"),
    ("DEPORTE", "DEPORTE COMPETITIVO"): ("DEPORTE", "COMPETITIVO"),
    ("DEPORTE", "ADMINISTRACION DEPORTES Y RECREACION"): (
        "DEPORTE",
        "ADMINISTRACION DEPORTE",
    ),
    (
        "TRANSPORTE",
        "TRANSPORTE URBANO, VIALIDAD PEATONAL",
    ): ("TRANSPORTE", "TRANSPORTE URBANO, Y VIALIDAD PEATONAL"),
    (
        "TRANSPORTE",
        "TRANSPORTE MARITIMO, FLUVIAL Y LACUSTRE",
    ): ("TRANSPORTE", "TRANSPORTE MARITIMO, FLUVIAL Y LACUSTRE"),
    (
        "RECURSOS HIDRICOS",
        "DEFENSAS FLUVIALES, MARITIMAS Y CAUCES NATURALES",
    ): (
        "RECURSOS HIDRICOS",
        "DEFENSAS FLUVIALES, MARITIMAS Y CAUCES ARTIFICIALES *",
    ),
    (
        "RECURSOS HIDRICOS",
        "ADMINISTRACION AGUA POTABLE Y ALCANTARILLADO",
    ): ("RECURSOS HIDRICOS", "ADMINISTRACION RECURSOS HIDRICOS"),
}


def resolve_sector_subsector(sector: str | None, subsector: str | None) -> tuple[str, str]:
    """Resuelve sector/subsector BIP al par canónico de la taxonomía."""
    sector_norm = normalize_key(sector)
    subsector_norm = normalize_key(subsector)

    sector_norm = SECTOR_ALIASES.get(sector_norm, sector_norm)

    alias = SUBSECTOR_ALIASES.get((sector_norm, subsector_norm))
    if alias:
        return alias

    return sector_norm, subsector_norm
