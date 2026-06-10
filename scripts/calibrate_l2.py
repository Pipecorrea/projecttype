#!/usr/bin/env python3
"""Calibra umbrales L2 simulando sobre scores ya calculados."""

from __future__ import annotations

import argparse
from itertools import product

import polars as pl

from proyecttype.evaluation import NivelMatch, clasificar_match, load_submuestra
from proyecttype.paths import DEFAULT_OUTPUT_CASCADE_CSV, DEFAULT_SUBMUESTRA


def _simulate(
    df: pl.DataFrame,
    *,
    min_sim: float,
    min_margin: float,
) -> dict[str, float | int]:
    l2_won = 0
    l2_exact = 0
    l2_ayuda = 0
    l2_empeora = 0
    fin_exact = 0
    fin_asig = 0
    fin_exact_asig = 0

    for row in df.iter_rows(named=True):
        manual = row["tipo_proyecto"]
        l1_est = row["l1_estado"]
        l1_tipo = row["l1_tipo_nombre"]
        sim = row["l2_similitud"]
        marg = row["l2_margen"]
        l2_tipo = row["l2_tipo_nombre"]

        l2_assign = (
            l1_est in ("ambiguo", "sin_match")
            and sim is not None
            and sim >= min_sim
            and marg is not None
            and marg >= min_margin
        )

        if l2_assign:
            fin_est = "asignado"
            fin_tipo = l2_tipo
            l2_won += 1
            m_fin = clasificar_match(fin_tipo, manual, l1_estado=fin_est).value
            m_l1 = clasificar_match(l1_tipo, manual, l1_estado=l1_est).value
            if m_fin == NivelMatch.COINCIDENCIA_EXACTA.value:
                l2_exact += 1
                if m_l1 != NivelMatch.COINCIDENCIA_EXACTA.value:
                    l2_ayuda += 1
            elif m_fin == NivelMatch.DISCREPANCIA.value:
                l2_empeora += 1
        else:
            fin_est = l1_est
            fin_tipo = l1_tipo

        m_fin = clasificar_match(fin_tipo, manual, l1_estado="asignado" if l2_assign else l1_est)
        if m_fin == NivelMatch.COINCIDENCIA_EXACTA.value:
            fin_exact += 1
        if l2_assign or l1_est == "asignado":
            fin_asig += 1
            if m_fin == NivelMatch.COINCIDENCIA_EXACTA.value:
                fin_exact_asig += 1

    return {
        "min_sim": min_sim,
        "min_margin": min_margin,
        "l2_won": l2_won,
        "l2_prec": l2_exact / l2_won if l2_won else 0.0,
        "l2_ayuda": l2_ayuda,
        "l2_empeora": l2_empeora,
        "net_l2": l2_ayuda - l2_empeora,
        "fin_exact": fin_exact,
        "fin_asig": fin_asig,
        "fin_prec": fin_exact_asig / fin_asig if fin_asig else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Grid search umbrales L2.")
    parser.add_argument("--cascade", default=str(DEFAULT_OUTPUT_CASCADE_CSV))
    parser.add_argument("--submuestra", default=str(DEFAULT_SUBMUESTRA))
    parser.add_argument("--top", type=int, default=15)
    args = parser.parse_args()

    man = load_submuestra(args.submuestra).with_columns(
        pl.col("codigo_bip").cast(pl.Utf8).str.strip_chars()
    ).filter(pl.col("tipo_proyecto").is_not_null())

    cas = pl.read_csv(args.cascade).with_columns(
        pl.col("Codigo BIP").cast(pl.Utf8).str.strip_chars().alias("codigo_bip")
    )
    df = man.select("codigo_bip", "tipo_proyecto").join(
        cas.select(
            "codigo_bip", "l1_estado", "l1_tipo_nombre",
            "l2_similitud", "l2_margen", "l2_tipo_nombre",
        ),
        on="codigo_bip",
        how="inner",
    )

    sim_grid = [0.42, 0.45, 0.48, 0.50, 0.52, 0.55, 0.58, 0.60]
    margin_grid = [0.03, 0.05, 0.08, 0.10, 0.12, 0.15, 0.18, 0.20]
    results = [_simulate(df, min_sim=s, min_margin=m) for s, m in product(sim_grid, margin_grid)]
    results.sort(
        key=lambda r: (r["fin_exact"], r["fin_prec"], r["net_l2"], -r["l2_empeora"]),
        reverse=True,
    )

    print(f"Proyectos con manual: {df.height}")
    print(f"\nTop {args.top} combinaciones:")
    for row in results[: args.top]:
        print(
            f"  sim>={row['min_sim']:.2f} marg>={row['min_margin']:.2f} | "
            f"exact={row['fin_exact']} prec={row['fin_prec']:.1%} | "
            f"L2={row['l2_won']} prec_l2={row['l2_prec']:.1%} | "
            f"neto={row['net_l2']:+d}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
