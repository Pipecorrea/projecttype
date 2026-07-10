"""Split dev/holdout del golden expost (PT-23)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

TAG_DEV = "dev"
TAG_HOLDOUT = "holdout"


def subsector_from_tags(tags: list[str]) -> str:
    for tag in tags:
        if tag.startswith("subsector:"):
            return tag.removeprefix("subsector:")
    return "_sin_subsector"


def _holdout_rank(caso_id: str, *, seed: int) -> str:
    return hashlib.sha256(f"{seed}:{caso_id}".encode()).hexdigest()


def assign_dev_holdout_tags(
    casos: list[dict[str, Any]],
    *,
    holdout_ratio: float = 0.2,
    seed: int = 42,
) -> list[dict[str, Any]]:
    """Asigna tags ``dev`` o ``holdout`` de forma estratificada por subsector.

    Cada caso conserva sus tags previos (p. ej. ``expost``, ``subsector:…``).
    """
    if not 0.0 < holdout_ratio < 1.0:
        raise ValueError(f"holdout_ratio debe estar en (0, 1); recibido {holdout_ratio}")

    by_subsector: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for caso in casos:
        tags = list(caso.get("tags") or [])
        by_subsector[subsector_from_tags(tags)].append(caso)

    out: list[dict[str, Any]] = []
    for _subsector, group in sorted(by_subsector.items()):
        ranked = sorted(group, key=lambda c: _holdout_rank(str(c["caso_id"]), seed=seed))
        n = len(ranked)
        if n == 1:
            n_holdout = 0
        elif n == 2:
            n_holdout = 1
        else:
            n_holdout = max(1, round(n * holdout_ratio))
            n_holdout = min(n_holdout, n - 1)
        holdout_ids = {str(c["caso_id"]) for c in ranked[:n_holdout]}
        for caso in group:
            tags = [t for t in (caso.get("tags") or []) if t not in (TAG_DEV, TAG_HOLDOUT)]
            split = TAG_HOLDOUT if str(caso["caso_id"]) in holdout_ids else TAG_DEV
            tagged = {**caso, "tags": [*tags, split]}
            out.append(tagged)

    out.sort(key=lambda c: str(c["caso_id"]))
    return out


def split_summary(casos: list[dict[str, Any]]) -> dict[str, int]:
    """Conteos por tag de split (y subsectores distintos por split)."""
    dev = holdout = 0
    dev_sub: set[str] = set()
    holdout_sub: set[str] = set()
    for caso in casos:
        tags = caso.get("tags") or []
        sub = subsector_from_tags(tags)
        if TAG_DEV in tags:
            dev += 1
            dev_sub.add(sub)
        if TAG_HOLDOUT in tags:
            holdout += 1
            holdout_sub.add(sub)
    return {
        "dev": dev,
        "holdout": holdout,
        "subsectores_dev": len(dev_sub),
        "subsectores_holdout": len(holdout_sub),
    }
