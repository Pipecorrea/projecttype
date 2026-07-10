"""PT-18 — gate de publicación: rechaza filas no verificables antes del upsert.

Lógica pura (sin IO ni LLM). Valida filas de ``enr_tipo_proyecto`` según el
contrato SC-13, la taxonomía y la regla D-6 (EBI canónico sin dígito verificador).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import polars as pl

from projecttype.inference_metadata import EVIDENCIA_MAX_CHARS

_MOTIVO_CLAVE = "clave_no_canonica"
_MOTIVO_TIPO = "tipo_fuera_de_taxonomia"
_MOTIVO_MODELO = "modelo_ausente"
_MOTIVO_PROMPT = "prompt_version_ausente"
_MOTIVO_TAXONOMY = "taxonomy_hash_ausente"
_MOTIVO_ENRICHER = "enricher_version_ausente"
_MOTIVO_NIVEL = "nivel_asignacion_invalido"
_MOTIVO_EVIDENCIA = "evidencia_excede_limite"
_MOTIVO_REVISOR = "revisor_ausente_con_validacion"

_NIVELES_VALIDOS = frozenset({"L1", "L2", "L3", "humano", "residual"})
_EBI_CANONICO = re.compile(r"^\d+$")

_TIPO_IDS: frozenset[str] | None = None


@dataclass(frozen=True, slots=True)
class ResultadoGate:
    """Resultado del gate sobre un DataFrame de publicación."""

    filas_validas: pl.DataFrame
    filas_rechazadas: tuple[tuple[int, tuple[str, ...]], ...]
    resumen: dict[str, int]


class StoreGateRejectedError(Exception):
    """Publicación abortada: filas no verificables superan el umbral permitido."""

    def __init__(self, resultado: ResultadoGate) -> None:
        self.resultado = resultado
        total = resultado.filas_validas.height + len(resultado.filas_rechazadas)
        n_rech = len(resultado.filas_rechazadas)
        super().__init__(
            f"Gate de publicación rechazó {n_rech}/{total} filas. "
            f"Resumen: {resultado.resumen}"
        )


def _valor_presente(val: object) -> bool:
    if val is None:
        return False
    if isinstance(val, float) and math.isnan(val):
        return False
    return not (isinstance(val, str) and not val.strip())


def _ebi_raw(row: Mapping[str, Any]) -> str:
    raw = row.get("_ebi_raw")
    if raw is not None and str(raw).strip():
        return str(raw).strip()
    return str(row.get("EBI_CODIGO") or "").strip()


def _ebi_canonica(ebi: str) -> bool:
    if not ebi:
        return False
    if "-" in ebi:
        return False
    return bool(_EBI_CANONICO.match(ebi))


def _tipo_ids_validos() -> frozenset[str]:
    global _TIPO_IDS
    if _TIPO_IDS is None:
        from projecttype.paths import DEFAULT_TAXONOMY
        from projecttype.taxonomy import Taxonomia

        tax = Taxonomia.from_yaml(DEFAULT_TAXONOMY)
        _TIPO_IDS = frozenset(t.tipo_id for t in tax.tipos)
    return _TIPO_IDS


def _validado_por_humano(row: Mapping[str, Any]) -> bool:
    val = row.get("validado_por_humano")
    return val in (True, "true", "True", 1, "1")


def validar_fila_tipo(row: Mapping[str, Any]) -> list[str]:
    """Motivos de rechazo para una fila de ``enr_tipo_proyecto``."""
    motivos: list[str] = []

    ebi = _ebi_raw(row)
    if not _ebi_canonica(ebi):
        motivos.append(_MOTIVO_CLAVE)

    tipo_id = row.get("tipo_final_id")
    if _valor_presente(tipo_id) and str(tipo_id) not in _tipo_ids_validos():
        motivos.append(_MOTIVO_TIPO)

    nivel = str(row.get("nivel_asignacion") or "").strip()
    if nivel not in _NIVELES_VALIDOS:
        motivos.append(_MOTIVO_NIVEL)

    evidencia = str(row.get("evidencia_resumen") or "")
    if len(evidencia) > EVIDENCIA_MAX_CHARS:
        motivos.append(_MOTIVO_EVIDENCIA)

    if nivel == "L3":
        modelo = row.get("modelo")
        if not _valor_presente(modelo) or str(modelo).strip() == "n/a":
            motivos.append(_MOTIVO_MODELO)
        if not _valor_presente(row.get("prompt_version")):
            motivos.append(_MOTIVO_PROMPT)
        if not _valor_presente(row.get("taxonomy_hash")):
            motivos.append(_MOTIVO_TAXONOMY)
        if not _valor_presente(row.get("enricher_version")):
            motivos.append(_MOTIVO_ENRICHER)

    if _validado_por_humano(row) and not _valor_presente(row.get("revisor")):
        motivos.append(_MOTIVO_REVISOR)

    return motivos


def aplicar_gate(df: pl.DataFrame) -> ResultadoGate:
    """Valida todas las filas y separa válidas de rechazadas."""
    if df.is_empty():
        return ResultadoGate(filas_validas=df, filas_rechazadas=(), resumen={})

    rechazadas: list[tuple[int, tuple[str, ...]]] = []
    resumen: dict[str, int] = {}
    indices_validos: list[int] = []

    for idx, row in enumerate(df.iter_rows(named=True)):
        motivos = tuple(validar_fila_tipo(row))
        if motivos:
            rechazadas.append((idx, motivos))
            for m in motivos:
                resumen[m] = resumen.get(m, 0) + 1
        else:
            indices_validos.append(idx)

    validas = df[indices_validos] if indices_validos else df.head(0)
    return ResultadoGate(
        filas_validas=validas,
        filas_rechazadas=tuple(rechazadas),
        resumen=resumen,
    )


def formatear_resumen_gate(resultado: ResultadoGate) -> str:
    """Resumen legible para CLI / logs."""
    total = resultado.filas_validas.height + len(resultado.filas_rechazadas)
    lineas = [
        f"Gate de publicación: {len(resultado.filas_rechazadas)}/{total} filas rechazadas",
    ]
    if resultado.resumen:
        lineas.append("Motivos:")
        for motivo, count in sorted(resultado.resumen.items()):
            lineas.append(f"  · {motivo}: {count}")
    return "\n".join(lineas)


def aplicar_gate_o_abortar(
    df: pl.DataFrame,
    *,
    allow_rejected_pct: float = 0.0,
) -> pl.DataFrame:
    """Ejecuta el gate; aborta si los rechazos superan ``allow_rejected_pct``."""
    resultado = aplicar_gate(df)
    if not resultado.filas_rechazadas:
        return df

    total = df.height
    rechazo_pct = len(resultado.filas_rechazadas) / total if total else 0.0
    if rechazo_pct > allow_rejected_pct:
        raise StoreGateRejectedError(resultado)

    return resultado.filas_validas
