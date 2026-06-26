# CLAUDE.md — ProyectType

> **Contexto del ecosistema:** lee primero **`ECOSISTEMA.md`** (eres un *enriquecedor*:
> clasificas el tipo de proyecto y escribes `enr_tipo_proyecto` al store). Estado vivo:
> `/Vs/ESTADO_ECOSISTEMA.md`. Rumbo: `/Vs/PROPUESTA_SOTA_2026-06.md`. Tareas de este
> repo: `AGENT_WORKPLAN.md`. Visión y alcance: `VISION.md`. Para humanos: `README.md`.

ProyectType = clasificador en cascada (L1 keywords → L2 embeddings → L3 LLM) que asigna
un `TipoProyecto` a cada BIP — un atributo que **no existe** en los datos oficiales.

## Conexión con el ecosistema

- **Camino de producción (PT-6):** `proyecttype enrich --from-store` — lee
  `CONSULTAS_EBI` del store (`store_input.py`), clasifica y publica
  `enr_tipo_proyecto` (`store_publish.py`). **SNI Intelligence lo consume**
  (`--filter tipo_proyecto=`). El camino CSV (`scripts/classify_cascade.py` +
  `scripts/enrich_to_store.py`, PT-5) sigue vivo para calibración/eval.
- ⚠️ Al escribir, normaliza **EBI_CODIGO sin dígito verificador** (`-N`) o el JOIN con EBI
  da 0 filas (lo protege `test_bip_code_normalized_for_join`). Regla D-6 del ecosistema.
- El cliente LLM L3 usa `sni_commons.llm` por defecto (adaptador `SniCommonsLLMClient`,
  PT-4); los clientes legacy (`GeminiClient`/`OpenAIClient`/`OllamaClient`) quedan como
  fallback con `use_sni_commons=False`.
- ⚠️ **Publish parcial:** publicar con `--limit` marca el resto como
  `_present_in_latest=false`; el CLI advierte y pide confirmación. Pilotos → `--dry-run`.

## Comandos

```bash
# Instalar (uv; requiere ../sni-commons como repo hermano)
uv sync --extra dev

# Verde antes de commitear = lo mismo que CI (bloqueante)
uv run pytest                          # 56 tests (PT-8: pytest, sin hacks de sys.path)
uv run ruff check src scripts tests
uv run mypy src                        # --strict

# Un archivo / un test
uv run pytest tests/test_classifier_l1.py
uv run pytest tests/test_classifier_l1.py::TestClassifierL1::test_biblioteca_asignada

# Producción: ciclo store→store (requiere BIP_DATA_DIR)
uv run proyecttype enrich --from-store [--enable-l3] [--limit N --dry-run] [--out x.csv]

# Camino CSV (calibración/eval)
uv run python scripts/classify_l1.py                     # solo L1
uv run python scripts/classify_cascade.py                # L1+L2
uv run python scripts/classify_cascade.py --enable-l3 --l3-provider google
uv run python scripts/classify_cascade.py --enable-l3 --l3-limit 100   # piloto L3
uv run python scripts/enrich_to_store.py data/output/resultados_l1_l2_l3.csv

# Evaluación / calibración / few-shot
uv run python scripts/build_revision_manual.py     # Excel L1 vs etiquetas manuales
uv run python scripts/build_few_shot_examples.py   # minar few-shot de la submuestra
uv run python scripts/calibrate_l2.py              # calibrar umbrales L2
uv run python scripts/l3_status.py                 # estado caché/progreso L3
```

## Arquitectura

### La cascada

Taxonomía en `data/taxonomy/taxonomia_tipos_proyecto.yaml` (326 tipos, 16 sectores,
84 subsectores), organizada por `(sector, subsector)`. Cada nivel corre **solo sobre
el residual** del anterior (`ambiguo` o `sin_match`):

| Nivel | Módulo | Método | Asigna cuando |
|---|---|---|---|
| L1 | `classifier_l1` + `scorer` | Keywords deterministas: fuertes/débiles, exclusiones, bonus por tipos compuestos | score ≥ 1.0 y margen ≥ 2.0 (`ScorerConfig`) |
| L2 | `classifier_l2` + `embeddings` | Coseno sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`) | similitud ≥ 0.48 y margen ≥ 0.12 (`L2Config`) |
| L3 | `classifier_l3` | LLM con lista cerrada de tipos del subsector, JSON estructurado (pydantic) | confianza ≥ 0.75 y `tipo_id` válido (`L3Config`) |

`ClassifierCascade` (fila a fila) · `pipeline_cascade.classify_cascade_dataframe`
(lote completo con Polars, integra el caché L3).

### Flujo de datos

```
PRODUCCIÓN:  store (CONSULTAS_EBI) → store_input → cascada → store_publish → enr_tipo_proyecto
CSV (eval):  data/raw/base_datos_extracto.csv → classify_cascade.py → resultados_l1_l2_l3.csv
```

### Módulos clave

- **`taxonomy.py`** — carga el YAML a `Taxonomia`; indexa `TipoProyecto` por clave
  normalizada `(sector, subsector)`.
- **`aliases.py`** — mapea nombres de sector/subsector del BIP (tipos, grafías
  alternativas) a claves canónicas. **Los mapeos nuevos van aquí.**
- **`scorer.py`** — motor de scoring L1; `ScorerConfig` controla pesos y umbrales.
- **`composite.py`** — detecta tipos compuestos ("JARDIN INFANTIL Y SALA CUNA"):
  bonus si todos los componentes tienen evidencia, castigo a los subtipos simples.
- **`embeddings.py`** / **`tipo_embedder.py`** — sentence-transformers con `lru_cache`;
  matrices de embeddings por subsector cacheadas en `data/taxonomy/embeddings_cache/`.
- **`llm_client.py`** — `SniCommonsLLMClient` (default, delega en `sni_commons.llm`)
  + clientes legacy + `MockLLMClient` para tests. Proveedor vía `LLMConfig.provider`.
- **`l3_cache.py`** — caché JSONL por `codigo_bip` (+ modelo): un BIP ya clasificado
  no re-paga la llamada LLM.
- **`prompts.py`** / `data/prompts/l3.yaml` — prompt L3 (rúbrica, edge cases);
  `few_shot_examples.yaml` (curado) + `few_shot_mined.yaml` (minado) se inyectan
  en cada prompt L3. **Reglas discriminantes** (`data/prompts/reglas_discriminantes.yaml`,
  vía `prompt_context.guia_discriminante_for_subsector`): guía de dominio por subsector
  confuso (hoy TRANSPORTE URBANO) inyectada como `contexto_adicional` de MÁXIMA prioridad
  — el saber del experto separado del pipeline, editable sin tocar código.
- **`store_input.py`** (PT-6) — `CONSULTAS_EBI` → input cascada; dedupe a una fila
  por proyecto (solicitud más reciente); claves → nombres vía `sni_commons.reference`.
- **`store_publish.py`** (PT-5) — proyecta al contrato `ENR_TIPO_PROYECTO_CONTRACT`,
  normaliza EBI_CODIGO, `upsert_dataframe` no destructivo con `writer=` (ledger v1.1).
- **`evaluation.py`** / **`few_shot_mining.py`** — comparación contra la submuestra
  manual (`data/raw/Submuestra_tp.xlsx`) y minería de few-shot desde discrepancias.

### Estados de clasificación

`EstadoClasificacion`: `asignado` (corta la cascada) · `ambiguo` / `sin_match`
(pasan al siguiente nivel) · `sin_taxonomia` (sin tipos para ese sector/subsector).

### Proveedores LLM (L3)

| Proveedor | Flag (scripts CSV) | Variables |
|---|---|---|
| Ollama (default local) | `--l3-provider ollama` | `OLLAMA_BASE_URL`, `OLLAMA_MODEL` |
| Google Gemini | `--l3-provider google` | `GEMINI_API_KEY`, `GEMINI_MODEL` (def: `gemini-2.5-flash`) |
| OpenAI | `--l3-provider openai` | `OPENAI_API_KEY` |

Free tier de Gemini ≈ 15 RPM; el cliente intercala 5 s entre llamadas
(`GEMINI_REQUEST_INTERVAL` para cambiarlo). La neutralidad de proveedor es
estratégica: el proveedor ministerial sigue indefinido (PROPUESTA §4.0).

### Tests

**pytest** (PT-8; `pythonpath = ["src"]` en pyproject, sin hacks de `sys.path`).
56 tests; la taxonomía YAML debe estar presente para la mayoría. mypy `--strict`
y ruff limpios — los tres bloqueantes en CI (`.github/workflows/ci.yml`, que
también clona `../sni-commons` con `ECOSYSTEM_PAT`).
