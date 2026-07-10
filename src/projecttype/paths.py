"""Rutas canónicas del proyecto."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
GOLDEN_DIR = DATA_DIR / "golden"
TAXONOMY_DIR = DATA_DIR / "taxonomy"
OUTPUT_DIR = DATA_DIR / "output"
DOCS_DIR = PROJECT_ROOT / "docs"
EVAL_DIR = DOCS_DIR / "eval"

DEFAULT_TAXONOMY = TAXONOMY_DIR / "taxonomia_tipos_proyecto.yaml"
DEFAULT_INPUT_CSV = RAW_DIR / "base_datos_extracto.csv"
DEFAULT_EXPOST_DB = RAW_DIR / "informe_expost.duckdb"
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
