"""Rutas canónicas del proyecto."""

from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
GOLDEN_DIR = DATA_DIR / "golden"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
OUTPUT_DIR = DATA_DIR / "output"
DOCS_DIR = PROJECT_ROOT / "docs"
EVAL_DIR = DOCS_DIR / "eval"

DEFAULT_TAXONOMY = TAXONOMY_DIR / "taxonomia_tipos_proyecto.yaml"
DEFAULT_GOLDEN = GOLDEN_DIR / "golden_tipo_proyecto.jsonl"
GOLDEN_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "golden_tipo_proyecto_fixture.yaml"
DEFAULT_UMBRALES = GOLDEN_DIR / "umbrales.yaml"
DEFAULT_OUTPUT_CSV = OUTPUT_DIR / "resultados_l1.csv"
DEFAULT_OUTPUT_CASCADE_CSV = OUTPUT_DIR / "resultados_l1_l2.csv"
DEFAULT_OUTPUT_CASCADE_L3_CSV = OUTPUT_DIR / "resultados_l1_l2_l3.csv"
DEFAULT_L3_PROGRESS_JSONL = OUTPUT_DIR / "l3_progress.jsonl"
DEFAULT_L3_CACHE_JSONL = OUTPUT_DIR / "l3_cache.jsonl"
DEFAULT_REVISION_XLSX = OUTPUT_DIR / "revision_manual_l1.xlsx"
DEFAULT_EMBEDDINGS_CACHE = TAXONOMY_DIR / "embeddings_cache"
DEFAULT_L3_PROMPTS = PROJECT_ROOT / "data" / "prompts" / "l3.yaml"
DEFAULT_FEW_SHOT_MINED = PROJECT_ROOT / "data" / "prompts" / "few_shot_mined.yaml"
PROMPTS_DIR = PROJECT_ROOT / "data" / "prompts"


def _ensure_dotenv() -> None:
    """Carga ``.env`` de la raíz si ``BIP_DATA_DIR`` aún no está en el entorno."""
    if os.environ.get("BIP_DATA_DIR"):
        return
    env_path = PROJECT_ROOT / ".env"
    if not env_path.is_file():
        return
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(env_path)


def bip_data_root() -> Path | None:
    """Directorio de trabajo del ecosistema (D-11); ``None`` si no está configurado."""
    _ensure_dotenv()
    raw = os.environ.get("BIP_DATA_DIR", "").strip()
    if not raw:
        return None
    return Path(raw).expanduser()


def raw_dir() -> Path:
    """Entrada voluminosa: ``<BIP_DATA_DIR>/projecttype`` o ``data/raw/`` en el repo."""
    root = bip_data_root()
    if root is not None:
        return root / "projecttype"
    return DATA_DIR / "raw"


def default_input_csv() -> Path:
    return raw_dir() / "base_para_tp_input.csv"


def default_expost_db() -> Path:
    return raw_dir() / "informe_expost.duckdb"


def __getattr__(name: str) -> Path:
    if name == "RAW_DIR":
        return raw_dir()
    if name == "DEFAULT_INPUT_CSV":
        return default_input_csv()
    if name == "DEFAULT_EXPOST_DB":
        return default_expost_db()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
