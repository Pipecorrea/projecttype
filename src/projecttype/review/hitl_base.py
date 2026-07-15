"""Base común para stores HITL (persistencia JSONL). Adaptado de OBSRATE.

`JsonlHitlStore[TRecord]` da la mecánica de carga/persistencia atómica de
registros llaveados; el store concreto (veredictos de tipo) define solo cómo
serializar y cuál es la clave.
"""

from __future__ import annotations

import json
import unicodedata
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def normalize_text(text: str) -> str:
    """Minúsculas sin tildes, para búsqueda consistente."""
    nfkd = unicodedata.normalize("NFKD", text or "")
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower()


class JsonlHitlStore[TRecord](ABC):
    """Persistencia JSONL compartida: carga, export y reescritura consolidada."""

    def __init__(self, persist_path: Path) -> None:
        self.persist_path = persist_path.resolve()

    @abstractmethod
    def record_key(self, record: TRecord) -> str:
        """Clave única del registro (p.ej. ebi_codigo)."""

    @abstractmethod
    def record_to_dict(self, record: TRecord) -> dict[str, Any]:
        """Serializa un registro a dict JSON-compatible."""

    @abstractmethod
    def record_from_dict(self, data: dict[str, Any]) -> TRecord:
        """Deserializa un registro desde dict."""

    def load_records(self) -> dict[str, TRecord]:
        if not self.persist_path.is_file():
            return {}
        out: dict[str, TRecord] = {}
        for line in self.persist_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = self.record_from_dict(json.loads(line))
            out[self.record_key(rec)] = rec
        return out

    def persist_records(self, records: dict[str, TRecord]) -> None:
        self.persist_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps(self.record_to_dict(r), ensure_ascii=False) for r in records.values()]
        self.persist_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def export_sorted(self, records: dict[str, TRecord]) -> list[TRecord]:
        return sorted(records.values(), key=self.record_key)

    @staticmethod
    def now_utc() -> datetime:
        return datetime.now(tz=UTC)
