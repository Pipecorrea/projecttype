"""Reporter de avance para lotes L3."""

from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import TextIO

ProgressCallback = Callable[[int, int, str | None], None]


@dataclass
class BatchProgress:
    """Muestra avance periódico en consola y opcionalmente en archivo JSONL."""

    total: int
    label: str = "L3"
    interval: int = 1
    stream: TextIO = field(default_factory=lambda: sys.stderr)
    log_path: Path | None = None
    _done: int = 0
    _started: float = field(default_factory=time.monotonic)

    def update(self, n: int = 1, *, codigo_bip: str | None = None) -> None:
        if self.total <= 0:
            return
        self._done += n
        elapsed = time.monotonic() - self._started
        rate = self._done / elapsed if elapsed > 0 else 0.0
        eta = (self.total - self._done) / rate if rate > 0 else 0.0
        pct = 100 * self._done / self.total
        codigo = f" | {codigo_bip}" if codigo_bip else ""
        line = (
            f"{self.label}: {self._done}/{self.total} ({pct:5.1f}%)"
            f" | {elapsed:,.0f}s | ETA {eta:,.0f}s{codigo}"
        )

        self._append_log(
            done=self._done,
            total=self.total,
            pct=pct,
            elapsed_s=round(elapsed, 1),
            eta_s=round(eta, 1),
            codigo_bip=codigo_bip,
        )

        if self._done % self.interval != 0 and self._done != self.total:
            return

        if self.stream.isatty():
            print(f"\r{line}", end="", file=self.stream, flush=True)
        else:
            print(line, file=self.stream, flush=True)
        if self._done >= self.total:
            print(file=self.stream)

    def _append_log(
        self,
        *,
        done: int,
        total: int,
        pct: float,
        elapsed_s: float,
        eta_s: float,
        codigo_bip: str | None,
    ) -> None:
        if self.log_path is None:
            return
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "done": done,
            "total": total,
            "pct": round(pct, 2),
            "elapsed_s": elapsed_s,
            "eta_s": eta_s,
            "codigo_bip": codigo_bip,
        }
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")

    def as_callback(self) -> ProgressCallback:
        def _cb(done: int, total: int, codigo_bip: str | None) -> None:
            del total
            delta = done - self._done
            if delta > 0:
                self.update(delta, codigo_bip=codigo_bip)

        return _cb
