"""Embeddings precalculados de tipos de proyecto."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np

from .embeddings import L2Config, encode_texts
from .taxonomy import Taxonomia, TipoProyecto
from .text_utils import join_fields


def build_tipo_text(tipo: TipoProyecto, *, max_chars: int = 1500) -> str:
    keywords = join_fields(
        " ".join(tipo.keywords_fuertes),
        " ".join(tipo.keywords_debiles),
    )
    text = f"{tipo.nombre}. {tipo.definicion}"
    if keywords:
        text = f"{text} Palabras clave: {keywords}"
    return text[:max_chars]


def build_project_text(
    *,
    nombre: str = "",
    descripcion: str = "",
    justificacion: str = "",
    descriptores: str = "",
    max_chars: int = 6000,
) -> str:
    return join_fields(nombre, descripcion, justificacion, descriptores)[:max_chars]


def _cache_paths(cache_dir: Path, model_name: str, fingerprint: str) -> tuple[Path, Path]:
    safe_model = model_name.replace("/", "_")
    base = cache_dir / f"tipos_{safe_model}_{fingerprint}"
    return base.with_suffix(".npz"), base.with_suffix(".json")


def taxonomy_fingerprint(taxonomy_path: Path) -> str:
    digest = hashlib.md5(taxonomy_path.read_bytes()).hexdigest()
    return digest[:16]


class TipoEmbeddingStore:
    """Matriz de embeddings por tipo_id con caché en disco."""

    def __init__(
        self,
        taxonomia: Taxonomia,
        *,
        config: L2Config | None = None,
        taxonomy_path: Path | None = None,
        cache_dir: Path | None = None,
    ) -> None:
        self.taxonomia = taxonomia
        self.config = config or L2Config()
        self.taxonomy_path = taxonomy_path
        self.cache_dir = cache_dir
        self.tipo_ids: list[str] = []
        self._matrix: np.ndarray | None = None
        self._by_id: dict[str, int] = {}
        self._build()

    @classmethod
    def from_yaml(
        cls,
        taxonomy_path: Path,
        *,
        config: L2Config | None = None,
        cache_dir: Path | None = None,
    ) -> TipoEmbeddingStore:
        tax = Taxonomia.from_yaml(taxonomy_path)
        return cls(
            tax,
            config=config,
            taxonomy_path=Path(taxonomy_path),
            cache_dir=cache_dir,
        )

    def _build(self) -> None:
        tipos = self.taxonomia.tipos
        self.tipo_ids = [t.tipo_id for t in tipos]
        self._by_id = {tipo_id: idx for idx, tipo_id in enumerate(self.tipo_ids)}

        if self.cache_dir and self.taxonomy_path:
            loaded = self._load_cache()
            if loaded is not None:
                self._matrix = loaded
                return

        texts = [
            build_tipo_text(t, max_chars=self.config.max_tipo_chars)
            for t in tipos
        ]
        self._matrix = encode_texts(
            texts,
            model_name=self.config.model_name,
            batch_size=self.config.batch_size,
        )
        if self.cache_dir and self.taxonomy_path:
            self._save_cache()

    def _load_cache(self) -> np.ndarray | None:
        assert self.cache_dir and self.taxonomy_path
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = taxonomy_fingerprint(self.taxonomy_path)
        npz_path, meta_path = _cache_paths(self.cache_dir, self.config.model_name, fingerprint)
        if not npz_path.exists() or not meta_path.exists():
            return None
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("tipo_ids") != self.tipo_ids:
            return None
        data = np.load(npz_path)
        return np.asarray(data["embeddings"], dtype=np.float32)

    def _save_cache(self) -> None:
        assert self.cache_dir and self.taxonomy_path and self._matrix is not None
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        fingerprint = taxonomy_fingerprint(self.taxonomy_path)
        npz_path, meta_path = _cache_paths(self.cache_dir, self.config.model_name, fingerprint)
        np.savez_compressed(npz_path, embeddings=self._matrix)
        meta_path.write_text(
            json.dumps(
                {
                    "model_name": self.config.model_name,
                    "tipo_ids": self.tipo_ids,
                    "fingerprint": fingerprint,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    def matrix_for_tipos(self, tipos: list[TipoProyecto]) -> tuple[list[TipoProyecto], np.ndarray]:
        if self._matrix is None:
            raise RuntimeError("Embeddings no inicializados")
        ordered: list[TipoProyecto] = []
        rows: list[int] = []
        for tipo in tipos:
            idx = self._by_id.get(tipo.tipo_id)
            if idx is None:
                continue
            ordered.append(tipo)
            rows.append(idx)
        if not rows:
            return [], np.empty((0, 0), dtype=np.float32)
        return ordered, self._matrix[np.array(rows, dtype=np.int64)]
