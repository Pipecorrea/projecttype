"""Backend de embeddings para similitud semántica (Nivel 2)."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from numpy.typing import NDArray
    from sentence_transformers import SentenceTransformer


DEFAULT_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


@dataclass(frozen=True)
class L2Config:
    model_name: str = DEFAULT_MODEL
    min_similarity: float = 0.48
    min_margin: float = 0.12
    max_project_chars: int = 6000
    max_tipo_chars: int = 1500
    batch_size: int = 64


@lru_cache(maxsize=2)
def get_embedding_model(model_name: str = DEFAULT_MODEL) -> SentenceTransformer:
    from sentence_transformers import SentenceTransformer

    model: SentenceTransformer = SentenceTransformer(model_name)
    return model


def encode_texts(
    texts: list[str],
    *,
    model_name: str = DEFAULT_MODEL,
    batch_size: int = 64,
    normalize: bool = True,
) -> NDArray[np.float32]:
    model = get_embedding_model(model_name)
    vectors = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=False,
        convert_to_numpy=True,
        normalize_embeddings=normalize,
    )
    return np.asarray(vectors, dtype=np.float32)


def cosine_top2(
    query: NDArray[np.float32],
    matrix: NDArray[np.float32],
) -> tuple[float, float, int, int]:
    """Retorna sim1, sim2, idx1, idx2 para query normalizado vs matriz normalizada."""
    if matrix.size == 0:
        return 0.0, 0.0, -1, -1
    sims = matrix @ query
    if sims.shape[0] == 1:
        return float(sims[0]), 0.0, 0, -1
    idx = np.argpartition(sims, -2)[-2:]
    idx_sorted = idx[np.argsort(sims[idx])[::-1]]
    top, second = int(idx_sorted[0]), int(idx_sorted[1])
    return float(sims[top]), float(sims[second]), top, second


def cosine_top2_batch(
    queries: NDArray[np.float32],
    matrix: NDArray[np.float32],
) -> tuple[NDArray[np.float32], NDArray[np.float32], NDArray[np.int64], NDArray[np.int64]]:
    sims = queries @ matrix.T
    n = sims.shape[1]
    top_idx = np.argmax(sims, axis=1)
    top_sim = sims[np.arange(len(sims)), top_idx]

    if n == 1:
        zeros = np.zeros(len(sims), dtype=np.float32)
        return top_sim.astype(np.float32), zeros, top_idx.astype(np.int64), np.full(len(sims), -1)

    sims_copy = sims.copy()
    sims_copy[np.arange(len(sims)), top_idx] = -2.0
    second_idx = np.argmax(sims_copy, axis=1)
    second_sim = sims[np.arange(len(sims)), second_idx]
    return (
        top_sim.astype(np.float32),
        second_sim.astype(np.float32),
        top_idx.astype(np.int64),
        second_idx.astype(np.int64),
    )
