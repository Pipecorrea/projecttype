"""Lectura/escritura versionada de prompts y config editable (base de PT-22).

Archivos EDITABLES desde la UI (cambian ``prompt_version``, mecanismo diseñado
para afinarse sin re-clasificar toda la cartera):
- ``l3`` → `data/prompts/l3.yaml` (system prompt, pasos de razonamiento, casos borde)
- ``reglas_discriminantes`` → guía experta por subsector confuso
- ``few_shot_examples`` → ejemplos curados

Archivo de SOLO LECTURA:
- ``taxonomia`` → editar los tipos/definiciones cambia ``taxonomy_hash`` e invalida
  caché/incremental/store (regla dura: solo en PT-22 con re-clasificación gobernada).
  Se expone para inspección; el write se rechaza con mensaje accionable.

Cada escritura hace *git write-through* (stage) para auditoría y registra la
versión (sha256 corto) en `data/config/prompt_versions.json`.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

from projecttype.paths import DATA_DIR, DEFAULT_TAXONOMY, PROJECT_ROOT, PROMPTS_DIR

ConfigKind = Literal["l3", "reglas_discriminantes", "few_shot_examples", "taxonomia"]

WRITABLE_KINDS: tuple[ConfigKind, ...] = ("l3", "reglas_discriminantes", "few_shot_examples")
READONLY_KINDS: tuple[ConfigKind, ...] = ("taxonomia",)
ALL_KINDS: tuple[ConfigKind, ...] = (*WRITABLE_KINDS, *READONLY_KINDS)

VERSIONS_PATH = DATA_DIR / "config" / "prompt_versions.json"

_PATHS: dict[ConfigKind, Path] = {
    "l3": PROMPTS_DIR / "l3.yaml",
    "reglas_discriminantes": PROMPTS_DIR / "reglas_discriminantes.yaml",
    "few_shot_examples": PROMPTS_DIR / "few_shot_examples.yaml",
    "taxonomia": DEFAULT_TAXONOMY,
}


class ConfigWriteError(RuntimeError):
    """Escritura rechazada (kind inválido o de solo lectura)."""


@dataclass(frozen=True, slots=True)
class ConfigFileInfo:
    kind: str
    path: str
    content: str
    version: str
    bytes: int
    writable: bool


def _hash_content(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:12]


def _rel_path(path: Path) -> str:
    """Ruta relativa a la raíz del repo, o absoluta si el archivo está fuera (tests)."""
    try:
        return str(path.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def _resolve_kind(kind: str) -> ConfigKind:
    if kind not in ALL_KINDS:
        raise ConfigWriteError(f"kind inválido: {kind!r}. Válidos: {', '.join(ALL_KINDS)}.")
    return kind


def read_config_file(kind: str) -> ConfigFileInfo:
    ck = _resolve_kind(kind)
    path = _PATHS[ck]
    if not path.is_file():
        raise FileNotFoundError(path)
    content = path.read_text(encoding="utf-8")
    return ConfigFileInfo(
        kind=ck,
        path=_rel_path(path),
        content=content,
        version=_hash_content(content),
        bytes=len(content.encode("utf-8")),
        writable=ck in WRITABLE_KINDS,
    )


def list_config_files() -> list[ConfigFileInfo]:
    out: list[ConfigFileInfo] = []
    for kind in ALL_KINDS:
        try:
            out.append(read_config_file(kind))
        except FileNotFoundError:
            continue
    return out


def _git_write_through(rel_path: str) -> bool:
    """Stage el archivo editado para auditoría (no commitea)."""
    try:
        add = subprocess.run(
            ["git", "add", rel_path],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        return add.returncode == 0
    except OSError:
        return False


def write_config_file(
    kind: str,
    content: str,
    *,
    record_version: bool = True,
    git_write_through: bool = True,
) -> ConfigFileInfo:
    ck = _resolve_kind(kind)
    if ck not in WRITABLE_KINDS:
        raise ConfigWriteError(
            f"'{ck}' es de solo lectura: editar la taxonomía cambia taxonomy_hash e "
            "invalida caché/incremental/store. Debe hacerse en PT-22 con re-clasificación."
        )
    path = _PATHS[ck]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    info = ConfigFileInfo(
        kind=ck,
        path=_rel_path(path),
        content=content,
        version=_hash_content(content),
        bytes=len(content.encode("utf-8")),
        writable=True,
    )
    if record_version:
        _append_version(info)
    if git_write_through:
        _git_write_through(info.path)
    return info


def _load_versions() -> dict[str, list[dict[str, str]]]:
    if not VERSIONS_PATH.is_file():
        return {}
    return cast(
        dict[str, list[dict[str, str]]],
        json.loads(VERSIONS_PATH.read_text(encoding="utf-8")),
    )


def _append_version(info: ConfigFileInfo) -> None:
    versions = _load_versions()
    entry = {
        "version": info.version,
        "path": info.path,
        "at": datetime.now(tz=UTC).isoformat(),
    }
    hist = versions.get(info.kind, [])
    if not hist or hist[-1].get("version") != info.version:
        hist.append(entry)
    versions[info.kind] = hist[-20:]  # últimas 20
    VERSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    VERSIONS_PATH.write_text(
        json.dumps(versions, indent=2, ensure_ascii=False), encoding="utf-8"
    )
