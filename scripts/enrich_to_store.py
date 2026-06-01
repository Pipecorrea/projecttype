"""PT-5 CLI — publica el tipo de proyecto clasificado al store canónico.

Lee un CSV de resultados de la cascada (el que produce classify_cascade.py:
`resultados_l1_l2_l3.csv`) y publica la columna tipo_proyecto a la tabla
`enr_tipo_proyecto` del store (BIP_DATA_DIR), de forma incremental no destructiva.

Uso:
    python scripts/enrich_to_store.py data/output/resultados_l1_l2_l3.csv
    python scripts/enrich_to_store.py <csv> --dry-run
    python scripts/enrich_to_store.py <csv> --data-dir /ruta/al/store
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import polars as pl

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from proyecttype.store_publish import publish_to_store  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description="Publica tipo_proyecto al store canónico.")
    ap.add_argument("resultados_csv", type=Path, help="CSV de salida de la cascada.")
    ap.add_argument("--data-dir", default=None, help="Store dir (o usa BIP_DATA_DIR).")
    ap.add_argument("--dry-run", action="store_true", help="No escribe; solo diagnostica.")
    args = ap.parse_args()

    if not args.resultados_csv.exists():
        ap.error(f"No existe el CSV: {args.resultados_csv}")

    df = pl.read_csv(args.resultados_csv, infer_schema_length=10000)
    diag = publish_to_store(df, data_dir=args.data_dir, dry_run=args.dry_run)
    print(diag.summary())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
