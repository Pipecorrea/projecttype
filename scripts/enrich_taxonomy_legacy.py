#!/usr/bin/env python3
"""Referencia de enriquecimiento legacy aplicado a taxonomia_tipos_proyecto.yaml.

Los cambios ya están integrados en el YAML (2026-05-26). Este módulo documenta
el mapeo tipo_id → keywords/exclusiones y puede re-aplicarse de forma idempotente
sobre una copia del YAML base si hace falta regenerar.

Uso: python scripts/enrich_taxonomy_legacy.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
TAXONOMY_PATH = ROOT / "data" / "taxonomy" / "taxonomia_tipos_proyecto.yaml"

# Exclusiones Fase 0 compartidas (legacy → excluye_si_contiene por tipo)
EXCLUYE_AGUA_POTABLE = [
    "riego",
    "pluvial",
    "alcantarillado",
    "aguas servidas",
    "fosa",
    "septico",
    "espigon",
    "defensa maritima",
    "aluvional",
    "aljibe",
]

EXCLUYE_EDUC_PREBASICA = [
    "tecnico profesional",
    "educacion superior",
    "museo",
    "casa de la cultura",
    "patrimonio",
]

EXCLUYE_SALUD_BC = [
    "alta complejidad",
    "media complejidad",
    "oncologico",
    "radioterapia",
    "angiografia",
    "dialisis",
    "samu",
    "centro regulador",
    "cenabast",
    "compin",
]

EXCLUYE_SALUD_MC = [
    "cesfam",
    "cecosf",
    "posta rural",
    "baja complejidad",
    "hospital familiar comunitario",
    "alta complejidad",
]

EXCLUYE_JUSTICIA_RA = [
    "fiscalia",
    "ministerio publico",
    "corte suprema",
    "registro civil",
    "asistencia menores",
    "servicio medico legal",
]

ENRICHMENTS: dict[str, dict] = {
    "RECURSOS_HIDRICOS.AGUA_POTABLE.SISTEMA_AGUA_POTABLE_RURAL": {
        "keywords_fuertes": ["apr", "sapr", "desalinizadora", "desaladora", "ssr", "comite", "colectivo", "servicio"],
        "keywords_debiles": ["aduccion", "arranque", "captacion"],
        "excluye_si_contiene": EXCLUYE_AGUA_POTABLE,
    },
    "RECURSOS_HIDRICOS.AGUA_POTABLE.RED_DE_AGUA_POTABLE_RURAL": {
        "keywords_fuertes": ["apr", "aduccion", "comite", "colectivo", "ssr"],
        "keywords_debiles": ["ampliacion", "extension"],
        "excluye_si_contiene": EXCLUYE_AGUA_POTABLE,
    },
    "RECURSOS_HIDRICOS.AGUA_POTABLE.SISTEMA_AGUA_POTABLE_URBANA": {
        "keywords_fuertes": ["empresa sanitaria", "concesionaria"],
        "keywords_debiles": ["arranque", "servicio"],
        "excluye_si_contiene": EXCLUYE_AGUA_POTABLE,
    },
    "RECURSOS_HIDRICOS.AGUA_POTABLE.RED_DE_AGUA_POTABLE_URBANA": {
        "keywords_fuertes": ["aduccion", "extension"],
        "keywords_debiles": ["ampliacion"],
        "excluye_si_contiene": EXCLUYE_AGUA_POTABLE,
    },
    "EDUCACION.EDUCACION_PREBASICA.JARDIN_INFANTIL": {
        "keywords_fuertes": ["prekinder", "parvulo", "parvularia", "vtf", "kinder"],
        "keywords_debiles": ["nivel medio", "nivel transicion", "prebasica", "parvulario", "jardines"],
        "excluye_si_contiene": EXCLUYE_EDUC_PREBASICA,
    },
    "EDUCACION.EDUCACION_PREBASICA.JARDIN_INFANTIL_Y_SALA_CUNA": {
        "keywords_fuertes": ["parvulo", "lactante"],
        "keywords_debiles": ["nivel medio", "recinto"],
        "excluye_si_contiene": EXCLUYE_EDUC_PREBASICA,
    },
    "EDUCACION.EDUCACION_PREBASICA.SALA_CUNA": {
        "keywords_fuertes": ["lactante", "lactantes", "salacuna"],
        "keywords_debiles": ["menor", "bebe"],
        "excluye_si_contiene": EXCLUYE_EDUC_PREBASICA + ["amamantamiento", "lactancia"],
    },
    "SALUD.BAJA_COMPLEJIDAD.HOSPITAL_DE_BAJA_COMPLEJIDAD": {
        "keywords_fuertes": ["hfc", "familiar comunitario", "hospital comunitario", "hospital familiar"],
        "keywords_debiles": ["mais", "aps"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.BAJA_COMPLEJIDAD.CENTRO_DE_SALUD_FAMILIAR_CESFAM": {
        "keywords_fuertes": ["ces", "consultorio", "centro salud familiar"],
        "keywords_debiles": ["ambulatoria", "promocion"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.BAJA_COMPLEJIDAD.CENTRO_COMUNITARIO_DE_SALUD_FAMILIAR_CECOSF": {
        "keywords_fuertes": ["centro comunitario salud", "centro comunitario"],
        "keywords_debiles": ["alero", "basicas"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.BAJA_COMPLEJIDAD.POSTA_RURAL": {
        "keywords_fuertes": ["postas", "posta salud rural"],
        "keywords_debiles": ["localidad", "derivando"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.BAJA_COMPLEJIDAD.SAPU__SUR": {
        "keywords_fuertes": [
            "sapu",
            "servicio urgencia rural",
            "urgencia rural",
            "atencion primaria urgencia",
        ],
        "keywords_debiles": ["adosado", "anexo", "emergencia"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
        "remove_keywords_fuertes": ["sur"],
    },
    "SALUD.BAJA_COMPLEJIDAD.SAR": {
        "keywords_fuertes": ["alta resolutividad", "alta resolucion", "servicio alta resolutividad"],
        "keywords_debiles": ["horario extendido", "complementa"],
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.BAJA_COMPLEJIDAD.OTROS_BAJA_COMPLEJIDAD": {
        "excluye_si_contiene": EXCLUYE_SALUD_BC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.EQUIPOSEQUIPAMIENTO_MEDIA_COMPLEJIDAD": {
        "keywords_fuertes": [
            "equipamiento",
            "adquisicion",
            "ambulancia",
            "ambul",
            "laparoscopio",
            "monitor",
            "respirador",
            "ventilador",
            "autoclave",
            "mesas quirurgicas",
            "ascensor",
            "scopio",
            "grafo",
            "ecotomografo",
            "colonoscopio",
            "esterilizador",
            "instrumental",
            "equip med",
        ],
        "keywords_debiles": ["reposicion equipo", "vehiculo transporte pacientes"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.CENTRO_REFERENCIA_SALUD_CRS": {
        "keywords_fuertes": ["centro referencia salud", "referencia secundaria"],
        "keywords_debiles": ["imagenologia", "examenes clinicos"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.CONSULTORIO_ESPECIALIDADES_CAE": {
        "keywords_fuertes": ["consultorio adosado", "consultorio especialidades", "consultorio externo"],
        "keywords_debiles": ["consul", "cons", "consult"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.UNIDAD_DE_TRATAMIENTO_INTERMEDIO_UTI": {
        "keywords_fuertes": ["uci", "upc", "cuidados intensivos", "unidad cuidados intensivos"],
        "keywords_debiles": ["cuidados intermedios", "paliativos"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.HOSPITAL_DE_MEDIANA_COMPLEJIDAD": {
        "keywords_fuertes": ["media complejidad", "mediana complejidad", "hospital mediana"],
        "keywords_debiles": ["hosp", "hos"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.CENTRO_DE_SALUD_MENTAL_COMUNITARIO_COSAM": {
        "keywords_fuertes": ["salud mental comunitario", "salud mental"],
        "keywords_debiles": ["psiquiatria", "psiquiatrico"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.CENTRO_DE_DIALISIS": {
        "keywords_fuertes": ["hemodialisis", "peritoneodialisis"],
        "keywords_debiles": ["sustitucion renal", "renal cronica"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.BASES_SAMU_Y_CENTROS_REGULADORES": {
        "keywords_fuertes": ["centro regulador", "atencion prehospitalaria", "prehospitalaria"],
        "keywords_debiles": ["rescue", "traslado paciente"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "SALUD.MEDIA_COMPLEJIDAD.OTROS_MEDIA_COMPLEJIDAD": {
        "keywords_debiles": ["consultorio", "clinico", "servicio salud"],
        "excluye_si_contiene": EXCLUYE_SALUD_MC,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.COMPLEJO_PENITENCIARIO_CP": {
        "keywords_fuertes": ["cp", "establecimiento penal", "colonia penal"],
        "keywords_debiles": ["penales", "carcel"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA + ["cip", "tribunal", "juzgado"],
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_DE_CUMPLIMIENTO_PENITENCIARIO_CCP": {
        "keywords_fuertes": ["cumplimiento penitenciario", "centro cumplimiento"],
        "keywords_debiles": ["condenados", "penas privativas"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_DE_DETENCION_PREVENTIVA_CDP": {
        "keywords_fuertes": ["detencion preventiva", "centro detencion"],
        "keywords_debiles": ["procesados", "imputados"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_PENITENCIARIO_FEMENINO_CPF": {
        "keywords_fuertes": ["penitenciario femenino", "seccion mujeres"],
        "keywords_debiles": ["cof", "imputadas"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.UNIDAD_ESPECIAL_DE_ALTA_SEGURIDAD_UEAS": {
        "keywords_fuertes": ["peligrosidad extrema"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.RED_CONTRA_INCENDIO_SUBSISTEMA_CERRADO": {
        "keywords_fuertes": ["red contra incendio", "subsistema cerrado"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_DE_EDUCACION_Y_TRABAJO_CET": {
        "keywords_fuertes": ["educacion trabajo", "trabajo productivo", "formacion laboral"],
        "keywords_debiles": ["capacitacion laboral", "trabajo regular"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_DE_REINSERCION_SOCIAL_CRS": {
        "keywords_fuertes": [
            "reincercion",
            "reisercion",
            "readaptacion",
            "centro abierto",
            "semiabierto",
            "medio libre",
            "centro readaptacion social",
        ],
        "keywords_debiles": ["seguimiento condenados", "beneficio reglamentario"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
    "JUSTICIA.REHABILITACION_ADULTOS.CENTRO_DE_APOYO_PARA_LA_INTEGRACION_SOCIAL_CAIS": {
        "keywords_fuertes": ["patronato", "post condena"],
        "keywords_debiles": ["apoyo reinsercion", "cumplido condenas"],
        "excluye_si_contiene": EXCLUYE_JUSTICIA_RA,
    },
}


def _merge_unique(existing: list, additions: list[str]) -> list[str]:
    seen = {str(x).strip().lower() for x in existing if x is not None and str(x).strip()}
    result = list(existing)
    for item in additions:
        key = item.strip().lower()
        if key and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def _apply_enrichment(tipo: dict, spec: dict) -> None:
    for remove in spec.get("remove_keywords_fuertes", []):
        tipo["keywords_fuertes"] = [k for k in tipo.get("keywords_fuertes", []) if k.lower() != remove.lower()]

    if "keywords_fuertes" in spec:
        tipo["keywords_fuertes"] = _merge_unique(tipo.get("keywords_fuertes", []), spec["keywords_fuertes"])
    if "keywords_debiles" in spec:
        debiles = tipo.get("keywords_debiles", [])
        if debiles == "[]":
            debiles = []
        tipo["keywords_debiles"] = _merge_unique(debiles if isinstance(debiles, list) else [], spec["keywords_debiles"])
    if "excluye_si_contiene" in spec:
        tipo["excluye_si_contiene"] = _merge_unique(
            tipo.get("excluye_si_contiene", []),
            spec["excluye_si_contiene"],
        )


def enrich_taxonomy(data: dict) -> int:
    updated = 0
    for sector in data.get("sectores", []):
        for subsector in sector.get("subsectores", []):
            for tipo in subsector.get("tipos", []):
                tipo_id = tipo.get("tipo_id")
                if tipo_id in ENRICHMENTS:
                    _apply_enrichment(tipo, ENRICHMENTS[tipo_id])
                    updated += 1
    return updated


def main() -> int:
    if not TAXONOMY_PATH.exists():
        print(f"ERROR: no existe {TAXONOMY_PATH}", file=sys.stderr)
        return 1

    data = yaml.safe_load(TAXONOMY_PATH.read_text(encoding="utf-8"))
    n = enrich_taxonomy(data)
    TAXONOMY_PATH.write_text(
        yaml.dump(data, allow_unicode=True, sort_keys=False, width=120, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"Enriquecidos {n} tipos en {TAXONOMY_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
