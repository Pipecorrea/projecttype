# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (no setup.py/pyproject.toml — install manually)
pip install -r requirements.txt

# Run all tests
python -m pytest tests/           # or: python -m unittest discover tests

# Run a single test file
python -m unittest tests/test_classifier_l1.py

# Run a single test case
python -m unittest tests.test_classifier_l1.TestClassifierL1.test_biblioteca_asignada

# L1-only classification
python scripts/classify_l1.py

# Cascade L1 → L2 (keywords + embeddings)
python scripts/classify_cascade.py

# Cascade L1 → L2 → L3 with Gemini (recommended — free tier)
python scripts/classify_cascade.py --enable-l3 --l3-provider google

# Cascade L1 → L2 → L3 with Ollama (local default)
python scripts/classify_cascade.py --enable-l3

# Pilot L3 on first 100 residual rows
python scripts/classify_cascade.py --enable-l3 --l3-provider google --l3-limit 100

# List installed Ollama models
python scripts/classify_cascade.py --list-ollama-models

# Build human-review Excel (L1 vs manual labels)
python scripts/build_revision_manual.py

# Mine few-shot examples from manual labels where L1 failed/was wrong
python scripts/build_few_shot_examples.py

# Calibrate L2 thresholds against manual labels
python scripts/calibrate_l2.py
```

## Architecture

### Classification cascade

The system classifies public investment projects (BIP) into a taxonomy of project types (`TipoProyecto`). The taxonomy is organised by `(sector, subsector)` and stored in `data/taxonomy/taxonomia_tipos_proyecto.yaml`. Three levels are applied in sequence; each level runs only on the *residual* of the previous one (`ambiguo` or `sin_match` outcomes):

| Level | Module | Method |
|---|---|---|
| L1 | `classifier_l1.ClassifierL1` | Keyword scoring (deterministic): strong/weak keywords, exclusion rules, composite-type bonuses |
| L2 | `classifier_l2.ClassifierL2` | Sentence-transformer cosine similarity (`paraphrase-multilingual-MiniLM-L12-v2`) |
| L3 | `classifier_l3.ClassifierL3` | LLM call (Gemini / Ollama / OpenAI) with structured JSON output |

`ClassifierCascade` (`classifier_cascade.py`) wires all three together for single-row classification. `pipeline_cascade.classify_cascade_dataframe` handles full-dataset batch execution using Polars.

### Key data flow

```
data/raw/base_datos_extracto.csv
  → classify_dataframe (L1)            → resultados_l1.csv
  → classify_cascade_dataframe (L1+L2) → resultados_l1_l2.csv
  → classify_cascade_dataframe (+L3)   → resultados_l1_l2_l3.csv
```

### Core modules

- **`taxonomy.py`** — loads YAML taxonomy into `Taxonomia`; indexes `TipoProyecto` by normalised `(sector, subsector)` key.
- **`aliases.py`** — maps BIP sector/subsector strings (with typos or alternate spellings) to canonical taxonomy keys. **Add new mappings here when BIP data uses non-canonical names.**
- **`scorer.py`** — L1 keyword scoring engine. `ScorerConfig` controls all score weights and thresholds.
- **`composite.py`** — auto-detects compound type names (e.g. "JARDIN INFANTIL Y SALA CUNA") and adjusts scores: bonus when all components are evidenced, penalty for the simple subtypes.
- **`embeddings.py`** — wraps `sentence_transformers` with an `lru_cache`; `L2Config` controls model and thresholds.
- **`tipo_embedder.py`** — builds and caches embedding matrices per subsector in `data/taxonomy/embeddings_cache/`.
- **`llm_client.py`** — three concrete clients (`GeminiClient`, `OpenAIClient`, `OllamaClient`) plus `MockLLMClient` for tests. Provider is selected at runtime via `LLMConfig.provider`.
- **`l3_cache.py`** — JSONL-backed cache keyed by `codigo_bip`; avoids re-calling the LLM for already-classified projects.
- **`prompts.py`** / **`data/prompts/l3.yaml`** — L3 system prompt, chain-of-thought structure, rubric and edge cases. `data/prompts/few_shot_examples.yaml` (curated) and `data/prompts/few_shot_mined.yaml` (auto-mined) supply few-shot examples injected into every L3 prompt.
- **`evaluation.py`** — compares L1 output against `data/raw/Submuestra_tp.xlsx` (manual labels); produces Excel with conditional formatting.
- **`few_shot_mining.py`** — mines new few-shot candidates from the manual-label submuestra, prioritising discrepancies and unclassified rows.

### Classification outcomes

`EstadoClasificacion`: `asignado` | `ambiguo` | `sin_match` | `sin_taxonomia`

- `asignado` — confident single classification; stops the cascade.
- `ambiguo` / `sin_match` — passes to the next level.
- `sin_taxonomia` — no taxonomy entry for this `(sector, subsector)`.

### LLM providers (L3)

| Provider | Flag | Env var |
|---|---|---|
| Ollama (default) | `--l3-provider ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| Google Gemini | `--l3-provider google` | `GEMINI_API_KEY`, `GEMINI_MODEL` (default: `gemini-2.5-flash`) |
| OpenAI | `--l3-provider openai` | `OPENAI_API_KEY` |

Gemini free tier limits to ~15 RPM; the client auto-inserts a 5-second delay between calls (override with `GEMINI_REQUEST_INTERVAL`).

### Tests

Tests use `unittest` (no pytest required). Each test file inserts `src/` into `sys.path` directly. The taxonomy YAML at `data/taxonomy/taxonomia_tipos_proyecto.yaml` must be present for most tests to run.
