"""Snapshot en memoria para la UI HITL: store (read-only) + CoT L3 + veredictos.

El server NUNCA escribe al store canónico desde aquí (D-13). Lee:
- `enr_tipo_proyecto` (propuestas del sistema con metadatos SC-13),
- `CONSULTAS_EBI` (contexto: nombre/sector/subsector/descripción),
- el caché L3 (chain-of-thought, más completo que `evidencia_resumen`),
y persiste los veredictos humanos en un JSONL aparte (`veredictos_tipo.jsonl`).
Las escrituras al store canónico van por el loop de salida (PT-21) vía
`store_publish` + gate, nunca desde el server.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from projecttype.inference_metadata import prompt_version, taxonomy_hash
from projecttype.review.hitl_base import JsonlHitlStore, normalize_text
from projecttype.review.schemas import (
    CatalogoResponse,
    CatalogoSector,
    CatalogoSubsector,
    CatalogoTipo,
    ItemDetail,
    ManualPendienteItem,
    ManualPendientesResponse,
    Origen,
    QueueItem,
    QueueResponse,
    ReviewSummary,
    RevisionTipoRecord,
    SaveVerdictRequest,
    SubsectorCobertura,
    SubsectoresResponse,
    Veredicto,
)
from projecttype.taxonomy import Taxonomia

_ENR_TABLE = "enr_tipo_proyecto"

# nivel_asignacion (store) → origen (UI)
_NIVEL_TO_ORIGEN: dict[str, Origen] = {
    "L1": "l1",
    "L2": "l2",
    "L3": "l3",
    "residual": "residual",
    "humano": "manual",
}


class VeredictosStore(JsonlHitlStore[RevisionTipoRecord]):
    """Persistencia JSONL de los veredictos (última decisión por EBI gana)."""

    def record_key(self, record: RevisionTipoRecord) -> str:
        return record.ebi_codigo

    def record_to_dict(self, record: RevisionTipoRecord) -> dict[str, Any]:
        return record.model_dump(mode="json")

    def record_from_dict(self, data: dict[str, Any]) -> RevisionTipoRecord:
        return RevisionTipoRecord.model_validate(data)


@dataclass
class _ProjectContext:
    ebi_codigo: str
    nombre: str = ""
    sector: str = ""
    subsector: str = ""
    descripcion: str = ""
    justificacion: str = ""


@dataclass
class _Proposal:
    """Propuesta del sistema para un BIP (fila de enr_tipo_proyecto)."""

    ebi_codigo: str
    origen: Origen
    tipo_id: str | None
    tipo_nombre: str | None
    confianza: float | None
    evidencia: str = ""
    modelo: str = ""


@dataclass
class TipoReviewStore:
    """Snapshot en memoria. Construir con :meth:`open`."""

    taxonomia: Taxonomia
    verdicts: VeredictosStore
    _proposals: dict[str, _Proposal] = field(default_factory=dict)
    _context: dict[str, _ProjectContext] = field(default_factory=dict)
    _cot: dict[str, str] = field(default_factory=dict)
    _secundarios: dict[str, list[str]] = field(default_factory=dict)
    _verdicts_by_ebi: dict[str, RevisionTipoRecord] = field(default_factory=dict)
    store_writer: str | None = None
    store_actualizado: str | None = None

    # ── construcción ───────────────────────────────────────────────

    @classmethod
    def open(
        cls,
        *,
        taxonomy_path: Path,
        verdicts_path: Path,
        data_dir: Path | None = None,
        l3_cache_path: Path | None = None,
    ) -> TipoReviewStore:
        taxonomia = Taxonomia.from_yaml(taxonomy_path)
        verdicts = VeredictosStore(verdicts_path)
        store = cls(taxonomia=taxonomia, verdicts=verdicts)
        store._load(data_dir=data_dir, l3_cache_path=l3_cache_path)
        return store

    def _load(self, *, data_dir: Path | None, l3_cache_path: Path | None) -> None:
        self._context = _load_ebi_context(data_dir)
        self._proposals = _load_proposals(data_dir, self)
        self._cot, self._secundarios = _load_l3_cot(l3_cache_path)
        self._verdicts_by_ebi = self.verdicts.load_records()

    def reload(self, *, data_dir: Path | None, l3_cache_path: Path | None) -> None:
        self._load(data_dir=data_dir, l3_cache_path=l3_cache_path)

    # ── lecturas para la API ───────────────────────────────────────

    def summary(self) -> ReviewSummary:
        por_origen: dict[str, int] = {}
        for prop in self._proposals.values():
            por_origen[prop.origen] = por_origen.get(prop.origen, 0) + 1
        por_veredicto: dict[str, int] = {}
        for rec in self._verdicts_by_ebi.values():
            por_veredicto[rec.veredicto.value] = por_veredicto.get(rec.veredicto.value, 0) + 1
        revisados = sum(1 for ebi in self._proposals if ebi in self._verdicts_by_ebi)
        return ReviewSummary(
            total_clasificados=len(self._proposals),
            revisados=revisados,
            pendientes=len(self._proposals) - revisados,
            por_origen=por_origen,
            por_veredicto=por_veredicto,
            taxonomy_hash=taxonomy_hash(),
            prompt_version=prompt_version(),
            store_writer=self.store_writer,
            store_actualizado=self.store_actualizado,
        )

    def _sorted_ebis(self) -> list[str]:
        # Confianza ascendente (lo más dudoso primero); sin confianza al final.
        def _key(ebi: str) -> tuple[float, str]:
            conf = self._proposals[ebi].confianza
            return (conf if conf is not None else 2.0, ebi)

        return sorted(self._proposals, key=_key)

    def queue(
        self,
        *,
        origen: str | None = None,
        subsector: str | None = None,
        estado: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> QueueResponse:
        sub_norm = normalize_text(subsector) if subsector else None
        filtered: list[str] = []
        for ebi in self._sorted_ebis():
            prop = self._proposals[ebi]
            if origen and prop.origen != origen:
                continue
            ctx = self._context.get(ebi)
            if sub_norm and (ctx is None or normalize_text(ctx.subsector) != sub_norm):
                continue
            revisado = ebi in self._verdicts_by_ebi
            if estado == "pendiente" and revisado:
                continue
            if estado == "revisado" and not revisado:
                continue
            filtered.append(ebi)
        total = len(filtered)
        page = filtered[offset : offset + limit]
        items = [self._queue_item(ebi) for ebi in page]
        return QueueResponse(items=items, total=total, offset=offset, limit=limit)

    def _queue_item(self, ebi: str) -> QueueItem:
        prop = self._proposals[ebi]
        ctx = self._context.get(ebi) or _ProjectContext(ebi_codigo=ebi)
        rec = self._verdicts_by_ebi.get(ebi)
        return QueueItem(
            ebi_codigo=ebi,
            nombre=ctx.nombre,
            sector=ctx.sector,
            subsector=ctx.subsector,
            origen=prop.origen,
            tipo_propuesto_id=prop.tipo_id,
            tipo_propuesto_nombre=prop.tipo_nombre,
            confianza_sistema=prop.confianza,
            revisado=rec is not None,
            veredicto=rec.veredicto if rec else None,
            revisor=rec.revisor if rec else None,
        )

    def item(self, ebi: str) -> ItemDetail | None:
        prop = self._proposals.get(ebi)
        if prop is None:
            return None
        ctx = self._context.get(ebi) or _ProjectContext(ebi_codigo=ebi)
        ordered = self._sorted_ebis()
        idx = ordered.index(ebi) if ebi in ordered else 0
        return ItemDetail(
            ebi_codigo=ebi,
            nombre=ctx.nombre,
            sector=ctx.sector,
            subsector=ctx.subsector,
            descripcion=ctx.descripcion,
            justificacion=ctx.justificacion,
            origen=prop.origen,
            tipo_propuesto_id=prop.tipo_id,
            tipo_propuesto_nombre=prop.tipo_nombre,
            confianza_sistema=prop.confianza,
            evidencia=prop.evidencia,
            cot=self._cot.get(ebi, ""),
            tipos_secundarios=self._secundarios.get(ebi, []),
            review=self._verdicts_by_ebi.get(ebi),
            index=idx,
            total=len(ordered),
        )

    # ── escritura de veredicto (JSONL, no toca el store canónico) ───

    def save_verdict(self, ebi: str, req: SaveVerdictRequest) -> RevisionTipoRecord:
        prop = self._proposals.get(ebi)
        ctx = self._context.get(ebi) or _ProjectContext(ebi_codigo=ebi)
        tipo_final_id = req.tipo_final_id
        tipo_final_nombre = self._nombre_de_tipo(tipo_final_id)
        if req.veredicto == Veredicto.ACEPTADO and tipo_final_id is None and prop is not None:
            tipo_final_id = prop.tipo_id
            tipo_final_nombre = prop.tipo_nombre
        record = RevisionTipoRecord(
            ebi_codigo=ebi,
            nombre=ctx.nombre,
            sector=ctx.sector,
            subsector=ctx.subsector,
            descripcion=ctx.descripcion,
            justificacion=ctx.justificacion,
            origen=prop.origen if prop else "manual",
            tipo_propuesto_id=prop.tipo_id if prop else None,
            tipo_propuesto_nombre=prop.tipo_nombre if prop else None,
            confianza_sistema=prop.confianza if prop else None,
            evidencia=prop.evidencia if prop else "",
            cot=self._cot.get(ebi, ""),
            veredicto=req.veredicto,
            tipo_final_id=tipo_final_id,
            tipo_final_nombre=tipo_final_nombre,
            notas=req.notas,
            revisor=req.revisor,
            revisado_en=self.verdicts.now_utc(),
            taxonomy_hash=taxonomy_hash(),
            prompt_version=prompt_version(),
            modelo=prop.modelo if prop else "",
            enricher_version="",
        )
        self._verdicts_by_ebi[ebi] = record
        self.verdicts.persist_records(self._verdicts_by_ebi)
        return record

    def _nombre_de_tipo(self, tipo_id: str | None) -> str | None:
        if not tipo_id:
            return None
        for tipo in self.taxonomia.tipos:
            if tipo.tipo_id == tipo_id:
                return tipo.nombre
        return None

    # ── clasificación manual ───────────────────────────────────────

    def subsectores(self) -> SubsectoresResponse:
        # (sector, subsector) display → conteos
        counts: dict[tuple[str, str], list[int]] = {}
        for ebi, ctx in self._context.items():
            if not ctx.subsector:
                continue
            key = (ctx.sector, ctx.subsector)
            slot = counts.setdefault(key, [0, 0])
            # "Clasificado" = tiene tipo del sistema (store) o veredicto humano.
            # Consistente con pendientes(), que excluye ambos.
            if ebi in self._proposals or ebi in self._verdicts_by_ebi:
                slot[0] += 1
            else:
                slot[1] += 1
        items: list[SubsectorCobertura] = []
        for (sector, subsector), (n_clasif, n_pend) in sorted(counts.items()):
            n_tipos = len(self.taxonomia.tipos_para(sector, subsector))
            items.append(
                SubsectorCobertura(
                    sector=sector,
                    subsector=subsector,
                    n_tipos=n_tipos,
                    n_clasificados=n_clasif,
                    n_pendientes=n_pend,
                )
            )
        # Orden: menor cobertura primero (más pendientes de clasificar a mano).
        items.sort(key=lambda s: (s.n_clasificados, -s.n_pendientes))
        return SubsectoresResponse(items=items, total=len(items))

    def pendientes(
        self, *, sector: str | None, subsector: str | None, offset: int = 0, limit: int = 50
    ) -> ManualPendientesResponse:
        sec_norm = normalize_text(sector) if sector else None
        sub_norm = normalize_text(subsector) if subsector else None
        matched: list[ManualPendienteItem] = []
        for ebi, ctx in self._context.items():
            if ebi in self._proposals or ebi in self._verdicts_by_ebi:
                continue
            if sec_norm and normalize_text(ctx.sector) != sec_norm:
                continue
            if sub_norm and normalize_text(ctx.subsector) != sub_norm:
                continue
            matched.append(
                ManualPendienteItem(
                    ebi_codigo=ebi,
                    nombre=ctx.nombre,
                    sector=ctx.sector,
                    subsector=ctx.subsector,
                    descripcion=ctx.descripcion,
                    justificacion=ctx.justificacion,
                )
            )
        matched.sort(key=lambda m: m.ebi_codigo)
        total = len(matched)
        return ManualPendientesResponse(
            items=matched[offset : offset + limit], total=total, offset=offset, limit=limit
        )

    # ── catálogo ───────────────────────────────────────────────────

    def catalogo(self) -> CatalogoResponse:
        by_sector: dict[str, dict[str, list[CatalogoTipo]]] = {}
        for tipo in self.taxonomia.tipos:
            sub_map = by_sector.setdefault(tipo.sector, {})
            sub_map.setdefault(tipo.subsector, []).append(
                CatalogoTipo(tipo_id=tipo.tipo_id, nombre=tipo.nombre, definicion=tipo.definicion)
            )
        sectores = [
            CatalogoSector(
                sector=sector,
                subsectores=[
                    CatalogoSubsector(subsector=sub, tipos=tipos)
                    for sub, tipos in sorted(sub_map.items())
                ],
            )
            for sector, sub_map in sorted(by_sector.items())
        ]
        return CatalogoResponse(
            sectores=sectores,
            n_tipos=self.taxonomia.n_tipos,
            n_subsectores=self.taxonomia.n_subsectores,
            taxonomy_hash=taxonomy_hash(),
        )


# ── loaders (perezosos: sin store no fallan, snapshot vacío) ────────


def _load_ebi_context(data_dir: Path | None) -> dict[str, _ProjectContext]:
    try:
        from projecttype.store_input import load_cascade_input_from_store

        df = load_cascade_input_from_store(data_dir)
    except Exception:  # noqa: BLE001 — sin store/tabla, contexto vacío (UI aún útil)
        return {}
    out: dict[str, _ProjectContext] = {}
    for row in df.iter_rows(named=True):
        ebi = str(row.get("Codigo BIP") or "").strip()
        if not ebi:
            continue
        out[ebi] = _ProjectContext(
            ebi_codigo=ebi,
            nombre=str(row.get("NOMBRE") or ""),
            sector=str(row.get("SECTOR") or ""),
            subsector=str(row.get("SUBSECTOR") or ""),
            descripcion=str(row.get("descripción") or ""),
            justificacion=str(row.get("justificacion_proyecto") or ""),
        )
    return out


def _load_proposals(data_dir: Path | None, store: TipoReviewStore) -> dict[str, _Proposal]:
    import os

    base = data_dir or os.environ.get("BIP_DATA_DIR")
    if not base:
        return {}
    try:
        from sni_commons.store import BipDataStore, StoreError

        bip = BipDataStore(Path(base))
        try:
            df = bip.read_polars(_ENR_TABLE, only_present=True)
        except StoreError:
            return {}
        last = bip.last_load(_ENR_TABLE)
        if last is not None:
            store.store_writer = str(last.get("writer") or "") or None
            loaded = last.get("loaded_at")
            store.store_actualizado = str(loaded) if loaded is not None else None
    except Exception:  # noqa: BLE001 — store no disponible, sin propuestas
        return {}
    out: dict[str, _Proposal] = {}
    cols = set(df.columns)
    for row in df.iter_rows(named=True):
        ebi = str(row.get("EBI_CODIGO") or "").strip()
        if not ebi:
            continue
        nivel = str(row.get("nivel_asignacion") or "") if "nivel_asignacion" in cols else ""
        out[ebi] = _Proposal(
            ebi_codigo=ebi,
            origen=_NIVEL_TO_ORIGEN.get(nivel, "residual"),
            tipo_id=_str_or_none(row.get("tipo_final_id")),
            tipo_nombre=_str_or_none(row.get("tipo_final_nombre")),
            confianza=_float_or_none(row.get("confianza")),
            evidencia=str(row.get("evidencia_resumen") or ""),
            modelo=str(row.get("modelo") or ""),
        )
    return out


def _load_l3_cot(l3_cache_path: Path | None) -> tuple[dict[str, str], dict[str, list[str]]]:
    if l3_cache_path is None or not l3_cache_path.is_file():
        return {}, {}
    import json

    cot: dict[str, str] = {}
    secundarios: dict[str, list[str]] = {}
    for line in l3_cache_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
        except json.JSONDecodeError:
            continue
        ebi = str(data.get("codigo_bip") or "").strip()
        if not ebi:
            continue
        razon = data.get("l3_razonamiento")
        if razon:
            cot[ebi] = str(razon)
        raw_sec = data.get("l3_tipos_secundarios_nombres")
        if raw_sec:
            secundarios[ebi] = [p.strip() for p in str(raw_sec).split("|") if p.strip()]
    return cot, secundarios


def _str_or_none(value: object) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: object) -> float | None:
    if value is None or not isinstance(value, int | float | str):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
