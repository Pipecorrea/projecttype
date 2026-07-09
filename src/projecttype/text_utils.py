"""Utilidades de normalización de texto para matching de keywords."""

from __future__ import annotations

import re
import unicodedata


def strip_accents(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text)
    return "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")


def normalize_key(text: str | None) -> str:
    """Normaliza claves sector/subsector para lookup."""
    if not text:
        return ""
    value = strip_accents(str(text).upper().strip())
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\s*,\s*", ", ", value)
    return value.strip()


def normalize_text(text: str | None) -> str:
    """Normaliza texto libre para búsqueda de keywords."""
    if not text:
        return ""
    value = strip_accents(str(text).lower())
    value = re.sub(r"[^\w\s]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_tipo_name(text: str | None) -> str:
    """Normaliza nombre de tipo de proyecto para comparación entre fuentes.

    Unifica variantes ortográficas equivalentes (p. ej. taxonomía MDSF vs etiquetado manual).
    Preserva ``/`` y ``y/o`` para tipos compuestos.
    """
    if not text:
        return ""
    raw = str(text)
    raw = re.sub(r"\s+y/o\s+", " __YO__ ", raw, flags=re.IGNORECASE)
    raw = re.sub(r"\s*/\s*", "/", raw.strip())
    value = strip_accents(raw).lower()
    value = re.sub(r"[^\w\s/]", " ", value, flags=re.UNICODE)
    value = value.replace("__yo__", "y/o")
    value = re.sub(r"\s+", " ", value)
    value = re.sub(r"\bestandard\b", "estandar", value)
    return value.strip()


_STOPWORDS = frozenset({"de", "del", "la", "las", "el", "los", "y", "o", "en", "para", "con"})


def contains_component(text_norm: str, part_norm: str) -> bool:
    """Match de componente: frase exacta o todos sus tokens significativos."""
    if contains_keyword(text_norm, part_norm):
        return True
    tokens = [token for token in part_norm.split() if token not in _STOPWORDS and len(token) > 2]
    if len(tokens) < 2:
        return False
    return all(contains_keyword(text_norm, token) for token in tokens)


def contains_keyword(text_norm: str, keyword_norm: str) -> bool:
    if not text_norm or not keyword_norm:
        return False
    if " " in keyword_norm:
        return keyword_norm in text_norm
    return re.search(rf"\b{re.escape(keyword_norm)}\b", text_norm) is not None


def join_fields(*fields: str | None, sep: str = " ") -> str:
    parts = [str(f).strip() for f in fields if f and str(f).strip()]
    return sep.join(parts)
