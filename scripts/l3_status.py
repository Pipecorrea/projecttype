#!/usr/bin/env python3
"""Muestra el avance actual de una corrida L3 (lee l3_progress.jsonl)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from proyecttype.paths import DEFAULT_L3_PROGRESS_JSONL


def _load_last(path: Path) -> dict | None:
    if not path.is_file():
        return None
    last: dict | None = None
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                last = json.loads(line)
    return last


def _fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(seconds))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def main() -> int:
    parser = argparse.ArgumentParser(description="Estado de avance L3")
    parser.add_argument(
        "-f",
        "--file",
        default=str(DEFAULT_L3_PROGRESS_JSONL),
        help="Archivo JSONL de progreso",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        help="Actualizar cada 5 s (Ctrl+C para salir)",
    )
    args = parser.parse_args()
    path = Path(args.file)

    def render() -> int:
        record = _load_last(path)
        if record is None:
            print(f"Sin avance en {path}")
            print("¿Está corriendo classify_cascade.py --enable-l3?")
            return 1
        done = record["done"]
        total = record["total"]
        pct = record["pct"]
        elapsed = _fmt_seconds(record["elapsed_s"])
        eta = _fmt_seconds(record["eta_s"])
        codigo = record.get("codigo_bip") or "—"
        ts = record.get("ts", "")
        print(f"L3: {done}/{total} ({pct:.1f}%)")
        print(f"  Transcurrido: {elapsed}  |  ETA: {eta}")
        print(f"  Último BIP:   {codigo}")
        if ts:
            print(f"  Actualizado:  {ts}")
        return 0

    if not args.watch:
        return render()

    import time

    try:
        while True:
            print("\033[2J\033[H", end="")
            code = render()
            if code != 0:
                return code
            time.sleep(5)
    except KeyboardInterrupt:
        print()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
