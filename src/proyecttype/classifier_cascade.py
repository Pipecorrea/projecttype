"""Orquestador cascada L1 → L2 → L3."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .classifier_l2 import ClassifierL2
from .classifier_l3 import ClassifierL3, L3Config
from .embeddings import L2Config
from .scorer import EstadoClasificacion, ProyectoTexto, ResultadoClasificacion
from .taxonomy import Taxonomia
from .text_utils import join_fields


@dataclass(frozen=True)
class CascadeResult:
    l1: ResultadoClasificacion
    l2: ResultadoClasificacion | None
    l3: ResultadoClasificacion | None
    final: ResultadoClasificacion
    l3_razonamiento: str = ""


class ClassifierCascade:
    """Cascada L1 → L2 → L3: cada nivel solo corre sobre el residual anterior."""

    RESIDUAL = frozenset({EstadoClasificacion.AMBIGUO, EstadoClasificacion.SIN_MATCH})

    def __init__(
        self,
        l1,
        l2: ClassifierL2,
        l3: ClassifierL3 | None = None,
    ) -> None:
        self.l1 = l1
        self.l2 = l2
        self.l3 = l3

    @classmethod
    def from_yaml(
        cls,
        taxonomy_path: str | Path,
        *,
        l1_config=None,
        l2_config: L2Config | None = None,
        l3_config: L3Config | None = None,
        cache_dir: Path | None = None,
        enable_l3: bool = False,
        l3_mock: bool = False,
    ) -> ClassifierCascade:
        from .classifier_l1 import ClassifierL1

        path = Path(taxonomy_path)
        tax = Taxonomia.from_yaml(path)
        l1 = ClassifierL1(tax, config=l1_config)
        l2 = ClassifierL2.from_yaml(path, config=l2_config, cache_dir=cache_dir)
        l3 = None
        if enable_l3:
            l3 = ClassifierL3.from_yaml(path, config=l3_config, mock=l3_mock)
        return cls(l1, l2, l3)

    def classify_row(
        self,
        *,
        sector: str | None,
        subsector: str | None,
        nombre: str | None = None,
        descripcion: str | None = None,
        justificacion: str | None = None,
        descriptor_1: str | None = None,
        descriptor_2: str | None = None,
        descriptor_3: str | None = None,
    ) -> CascadeResult:
        proyecto = ProyectoTexto(
            nombre=nombre or "",
            descripcion=descripcion or "",
            justificacion=justificacion or "",
            descriptores=join_fields(descriptor_1, descriptor_2, descriptor_3),
        )
        l1 = self.l1.classify_row(
            sector=sector,
            subsector=subsector,
            nombre=proyecto.nombre,
            descripcion=proyecto.descripcion,
            justificacion=proyecto.justificacion,
            descriptor_1=descriptor_1,
            descriptor_2=descriptor_2,
            descriptor_3=descriptor_3,
        )
        final = l1
        l2 = None
        l3 = None
        l3_razonamiento = ""

        if l1.estado in self.RESIDUAL:
            l2 = self.l2.classify_row(
                sector=sector,
                subsector=subsector,
                proyecto=proyecto,
            )
            if l2.estado == EstadoClasificacion.ASIGNADO:
                final = l2

        if self.l3 and final.estado in self.RESIDUAL:
            l3, l3_razonamiento = self.l3.classify_row(
                sector=sector,
                subsector=subsector,
                proyecto=proyecto,
                l1_tipo_id=l1.tipo_id,
                l1_tipo_nombre=l1.tipo_nombre,
                l1_estado=l1.estado.value,
                l2_tipo_id=l2.tipo_id if l2 else None,
                l2_tipo_nombre=l2.tipo_nombre if l2 else None,
                l2_estado=l2.estado.value if l2 else None,
            )
            if l3.estado == EstadoClasificacion.ASIGNADO:
                final = l3

        return CascadeResult(
            l1=l1,
            l2=l2,
            l3=l3,
            final=final,
            l3_razonamiento=l3_razonamiento,
        )
