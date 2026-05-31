#!/usr/bin/env python3
"""Análisis por sector: dónde L2 ayuda vs empeora respecto a L1."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import polars as pl

from proyecttype.evaluation import NivelMatch, clasificar_match, load_submuestra
from proyecttype.paths import (
    DEFAULT_OUTPUT_CASCADE_CSV,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_SUBMUESTRA,
)
from proyecttype.text_utils import normalize_tipo_name

EMPEORA = frozenset(
    {
        "l2_nuevo_error",
        "l2_empeora_ambiguo_correcto",
        "l2_empeora_vs_parcial",
        "l2_empeora_vs_l1",
    }
)


def _norm_tipo(value: str | None) -> str:
    if not value:
        return ""
    return normalize_tipo_name(str(value)).upper()


def _impacto_l2(
    *,
    l2_won: bool,
    match_l1: str,
    match_final: str,
    l1_top_exact: bool,
) -> str:
    if not l2_won:
        return "sin_cambio"
    if match_final == NivelMatch.COINCIDENCIA_EXACTA.value:
        if match_l1 != NivelMatch.COINCIDENCIA_EXACTA.value:
            return "l2_ayuda_exacta"
        return "l2_redundante_exacta"
    if match_final == NivelMatch.COINCIDENCIA_PARCIAL.value:
        if match_l1 not in (
            NivelMatch.COINCIDENCIA_EXACTA.value,
            NivelMatch.COINCIDENCIA_PARCIAL.value,
        ):
            return "l2_ayuda_parcial"
        return "l2_empeora_vs_l1"
    if l1_top_exact:
        return "l2_empeora_ambiguo_correcto"
    if match_l1 == NivelMatch.COINCIDENCIA_PARCIAL.value:
        return "l2_empeora_vs_parcial"
    return "l2_nuevo_error"


def build_analysis_df(
    resultados_l1: pl.DataFrame,
    resultados_cascade: pl.DataFrame,
    manual: pl.DataFrame,
) -> pl.DataFrame:
    man = manual.with_columns(
        pl.col("codigo_bip").cast(pl.Utf8).str.strip_chars(),
        pl.col("sector").cast(pl.Utf8),
        pl.col("subsector").cast(pl.Utf8),
    ).filter(pl.col("tipo_proyecto").is_not_null())

    l1 = resultados_l1.with_columns(
        pl.col("Codigo BIP").cast(pl.Utf8).str.strip_chars().alias("codigo_bip")
    )
    cas = resultados_cascade.with_columns(
        pl.col("Codigo BIP").cast(pl.Utf8).str.strip_chars().alias("codigo_bip")
    )

    merged = man.select("codigo_bip", "sector", "subsector", "tipo_proyecto").join(
        l1.select("codigo_bip", "l1_estado", "l1_tipo_nombre"),
        on="codigo_bip",
        how="inner",
    ).join(
        cas.select(
            "codigo_bip",
            "estado_final",
            "tipo_final_nombre",
            "nivel_final",
        ),
        on="codigo_bip",
        how="inner",
    )

    rows: list[dict] = []
    for row in merged.iter_rows(named=True):
        manual_tipo = row["tipo_proyecto"]
        l1_estado = row["l1_estado"]
        estado_final = row["estado_final"]
        match_l1 = clasificar_match(
            row["l1_tipo_nombre"], manual_tipo, l1_estado=l1_estado
        ).value
        match_final = clasificar_match(
            row["tipo_final_nombre"], manual_tipo, l1_estado=estado_final
        ).value
        l2_won = row["nivel_final"] == 2 and estado_final == "asignado"
        rows.append(
            {
                **row,
                "match_l1": match_l1,
                "match_final": match_final,
                "l1_asignado": l1_estado == "asignado",
                "final_asignado": estado_final == "asignado",
                "l1_top_exact": _norm_tipo(row["l1_tipo_nombre"]) == _norm_tipo(manual_tipo),
                "l1_residual": l1_estado in ("ambiguo", "sin_match"),
                "l2_won": l2_won,
                "impacto_l2": _impacto_l2(
                    l2_won=l2_won,
                    match_l1=match_l1,
                    match_final=match_final,
                    l1_top_exact=_norm_tipo(row["l1_tipo_nombre"]) == _norm_tipo(manual_tipo),
                ),
            }
        )
    return pl.DataFrame(rows)


def _pct(n: int, d: int) -> float:
    return round(100 * n / d, 1) if d else 0.0


def resumen_por_sector(df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict] = []
    for key, group in df.group_by("sector"):
        sector = key[0] if isinstance(key, tuple) else key
        n = group.height
        l1_exact = group.filter(pl.col("match_l1") == NivelMatch.COINCIDENCIA_EXACTA.value).height
        fin_exact = group.filter(pl.col("match_final") == NivelMatch.COINCIDENCIA_EXACTA.value).height
        l1_asig = group.filter(pl.col("l1_asignado")).height
        fin_asig = group.filter(pl.col("final_asignado")).height
        l1_exact_asig = group.filter(
            pl.col("l1_asignado")
            & (pl.col("match_l1") == NivelMatch.COINCIDENCIA_EXACTA.value)
        ).height
        fin_exact_asig = group.filter(
            pl.col("final_asignado")
            & (pl.col("match_final") == NivelMatch.COINCIDENCIA_EXACTA.value)
        ).height
        ayuda_e = group.filter(pl.col("impacto_l2") == "l2_ayuda_exacta").height
        empeora = group.filter(pl.col("impacto_l2").is_in(list(EMPEORA))).height
        rows.append(
            {
                "sector": str(sector),
                "n_manual": n,
                "l1_exact_pct": _pct(l1_exact, n),
                "final_exact_pct": _pct(fin_exact, n),
                "delta_exact": fin_exact - l1_exact,
                "l1_asignados": l1_asig,
                "final_asignados": fin_asig,
                "l1_prec_asignados": _pct(l1_exact_asig, l1_asig),
                "final_prec_asignados": _pct(fin_exact_asig, fin_asig),
                "residual_l1": group.filter(pl.col("l1_residual")).height,
                "l2_gano": group.filter(pl.col("l2_won")).height,
                "l2_ayuda_exacta": ayuda_e,
                "l2_ayuda_parcial": group.filter(pl.col("impacto_l2") == "l2_ayuda_parcial").height,
                "l2_empeora_total": empeora,
                "l2_nuevo_error": group.filter(pl.col("impacto_l2") == "l2_nuevo_error").height,
                "l2_empeora_amb_correcto": group.filter(
                    pl.col("impacto_l2") == "l2_empeora_ambiguo_correcto"
                ).height,
                "neto_l2": ayuda_e - empeora,
            }
        )
    return pl.DataFrame(rows).sort("delta_exact", descending=True)


def resumen_por_subsector(df: pl.DataFrame) -> pl.DataFrame:
    rows: list[dict] = []
    subset = df.filter(pl.col("l2_won"))
    for keys, group in subset.group_by(["sector", "subsector"]):
        ayuda = group.filter(pl.col("impacto_l2") == "l2_ayuda_exacta").height
        empeora = group.filter(pl.col("impacto_l2").is_in(list(EMPEORA))).height
        rows.append(
            {
                "sector": str(keys[0]),
                "subsector": str(keys[1]),
                "l2_gano": group.height,
                "l2_ayuda_exacta": ayuda,
                "l2_empeora": empeora,
                "neto_l2": ayuda - empeora,
            }
        )
    return pl.DataFrame(rows).sort("neto_l2", descending=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Análisis L2 por sector.")
    parser.add_argument("--l1", default=str(DEFAULT_OUTPUT_CSV))
    parser.add_argument("--cascade", default=str(DEFAULT_OUTPUT_CASCADE_CSV))
    parser.add_argument("--submuestra", default=str(DEFAULT_SUBMUESTRA))
    parser.add_argument(
        "--output-sector",
        default=str(ROOT / "data/output/l2_analisis_sector.csv"),
    )
    parser.add_argument(
        "--output-subsector",
        default=str(ROOT / "data/output/l2_analisis_subsector.csv"),
    )
    args = parser.parse_args()

    df = build_analysis_df(
        pl.read_csv(args.l1),
        pl.read_csv(args.cascade),
        load_submuestra(args.submuestra),
    )
    sector = resumen_por_sector(df)
    subsector = resumen_por_subsector(df)

    Path(args.output_sector).parent.mkdir(parents=True, exist_ok=True)
    sector.write_csv(args.output_sector)
    subsector.write_csv(args.output_subsector)

    print(f"Proyectos con etiqueta manual: {df.height}")
    print(f"L2 asignó final en: {df.filter(pl.col('l2_won')).height} proyectos")
    print("\nImpacto global L2:")
    for label in [
        "l2_ayuda_exacta",
        "l2_ayuda_parcial",
        "l2_nuevo_error",
        "l2_empeora_ambiguo_correcto",
        "l2_empeora_vs_parcial",
    ]:
        n = df.filter(pl.col("impacto_l2") == label).height
        print(f"  {label}: {n}")

    print("\nPor sector (delta exacta vs manual):")
    for row in sector.iter_rows(named=True):
        print(
            f"  {row['sector'][:42]:42s} n={row['n_manual']:4d} | "
            f"exact {row['l1_exact_pct']:5.1f}->{row['final_exact_pct']:5.1f}% "
            f"({row['delta_exact']:+d}) | "
            f"prec asignados {row['l1_prec_asignados']:.1f}->{row['final_prec_asignados']:.1f}% | "
            f"L2 neto {row['neto_l2']:+d}"
        )

    print(f"\nCSV sector: {args.output_sector}")
    print(f"CSV subsector: {args.output_subsector}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
