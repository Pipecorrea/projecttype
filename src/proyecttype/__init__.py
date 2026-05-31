"""Clasificación de tipos de proyecto BIP — cascada L1/L2/L3."""

from .classifier_l1 import ClassifierL1
from .classifier_l2 import ClassifierL2
from .classifier_l3 import ClassifierL3, L3Config
from .classifier_cascade import CascadeResult, ClassifierCascade
from .composite import CompositeIndex, TipoComponents, parse_tipo_components
from .embeddings import L2Config
from .llm_client import LLMConfig, create_llm_client, list_ollama_models
from .evaluation import (
    NivelMatch,
    build_revision_dataframe,
    clasificar_match,
    load_submuestra,
    resumen_nivel_match,
    save_revision_excel,
)
from .paths import (
    DEFAULT_INPUT_CSV,
    DEFAULT_OUTPUT_CSV,
    DEFAULT_OUTPUT_CASCADE_CSV,
    DEFAULT_OUTPUT_CASCADE_L3_CSV,
    DEFAULT_EMBEDDINGS_CACHE,
    DEFAULT_REVISION_XLSX,
    DEFAULT_SUBMUESTRA,
    DEFAULT_TAXONOMY,
    OUTPUT_DIR,
    PROJECT_ROOT,
    RAW_DIR,
    TAXONOMY_DIR,
)
from .pipeline import classify_csv, classify_dataframe, save_results
from .pipeline_cascade import classify_cascade_csv, classify_cascade_dataframe
from .scorer import EstadoClasificacion, ResultadoClasificacion, ScorerConfig
from .taxonomy import Taxonomia, TipoProyecto
from .tipo_embedder import TipoEmbeddingStore

__all__ = [
    "ClassifierL1",
    "ClassifierL2",
    "ClassifierL3",
    "ClassifierCascade",
    "CascadeResult",
    "CompositeIndex",
    "L2Config",
    "L3Config",
    "LLMConfig",
    "create_llm_client",
    "list_ollama_models",
    "TipoComponents",
    "TipoEmbeddingStore",
    "EstadoClasificacion",
    "NivelMatch",
    "ResultadoClasificacion",
    "ScorerConfig",
    "Taxonomia",
    "TipoProyecto",
    "PROJECT_ROOT",
    "RAW_DIR",
    "TAXONOMY_DIR",
    "OUTPUT_DIR",
    "DEFAULT_TAXONOMY",
    "DEFAULT_INPUT_CSV",
    "DEFAULT_SUBMUESTRA",
    "DEFAULT_OUTPUT_CSV",
    "DEFAULT_OUTPUT_CASCADE_CSV",
    "DEFAULT_OUTPUT_CASCADE_L3_CSV",
    "DEFAULT_EMBEDDINGS_CACHE",
    "DEFAULT_REVISION_XLSX",
    "build_revision_dataframe",
    "clasificar_match",
    "classify_csv",
    "classify_cascade_csv",
    "classify_cascade_dataframe",
    "classify_dataframe",
    "load_submuestra",
    "parse_tipo_components",
    "resumen_nivel_match",
    "save_results",
    "save_revision_excel",
]

__version__ = "0.1.0"
