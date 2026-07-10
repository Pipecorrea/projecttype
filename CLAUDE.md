# CLAUDE.md — ProjectType

> **Contexto del ecosistema:** lee primero **`ECOSISTEMA.md`** (eres un *enriquecedor*:
> clasificas el tipo de proyecto y escribes `enr_tipo_proyecto` al store). Estado vivo:
> `/Vs/ESTADO_ECOSISTEMA.md`. Rumbo: `/Vs/PROPUESTA_SOTA_2026-06.md`. Tareas:
> `AGENT_WORKPLAN.md`. Visión y alcance: `VISION.md`. **Diagnóstico SOTA y plan
> PT-15…PT-22:** `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`.

## Qué es

Clasificador en **cascada** (L1 keywords → L2 embeddings → L3 LLM) que asigna un
`TipoProyecto` a cada BIP — atributo que **no existe** en los datos oficiales.
SNI Intelligence lo consume (`--filter tipo_proyecto=`).

## Comandos

```bash
uv sync --extra dev     # requiere ../sni-commons como repo hermano

# Verde antes de commitear = CI (bloqueante; CI clona sni-commons con ECOSYSTEM_PAT)
uv run pytest && uv run ruff check src scripts tests && uv run mypy src   # mypy --strict

# Producción: ciclo store→store (requiere BIP_DATA_DIR)
uv run projecttype enrich --from-store | --from-selection <id>   # excluyentes; SNI publica sel_tipo_proyecto_<id>
                          [--enable-l3] [--limit N --dry-run]

# Camino CSV (calibración/eval; vivo a propósito, PT-5)
uv run python scripts/classify_cascade.py [--enable-l3 --l3-provider google --l3-limit 100]
uv run python scripts/enrich_to_store.py data/output/resultados_l1_l2_l3.csv

# Eval/calibración: scripts/{build_revision_manual,calibrate_l2,build_few_shot_examples,l3_status}.py
```

## Arquitectura

Taxonomía en `data/taxonomy/taxonomia_tipos_proyecto.yaml` (326 tipos, 16 sectores,
84 subsectores), indexada por `(sector, subsector)` en `taxonomy.py`. Cada nivel
corre **solo sobre el residual** del anterior (`ambiguo` o `sin_match`):

| Nivel | Módulos | Método | Asigna cuando |
|---|---|---|---|
| L1 | `classifier_l1` + `scorer` | keywords fuertes/débiles, exclusiones, bonus a tipos compuestos (`composite.py`) | score ≥ 1.0 y margen ≥ 2.0 (`ScorerConfig`) |
| L2 | `classifier_l2` + `embeddings` | coseno sentence-transformers multilingüe; matrices por subsector cacheadas en `data/taxonomy/embeddings_cache/` | similitud ≥ 0.48 y margen ≥ 0.12 (`L2Config`) |
| L3 | `classifier_l3` + `llm_client` | LLM con lista cerrada del subsector, JSON pydantic; caché JSONL por BIP+modelo (`l3_cache.py`) | confianza ≥ 0.75 y `tipo_id` válido (`L3Config`) |

Estados (`EstadoClasificacion`): `asignado` (corta la cascada) · `ambiguo`/`sin_match`
(pasan al siguiente nivel) · `sin_taxonomia`.

```
PRODUCCIÓN:  store (CONSULTAS_EBI) → store_input → cascada → store_publish → enr_tipo_proyecto
CSV (eval):  data/raw/base_datos_extracto.csv → classify_cascade.py → resultados_l1_l2_l3.csv
```

**Saber de dominio editable sin tocar código** (los ajustes van aquí, no en el código):

- `aliases.py` — nombres/grafías de sector-subsector del BIP → claves canónicas.
- `data/prompts/l3.yaml` + `few_shot_examples.yaml` (curado) + `few_shot_mined.yaml`
  (minado desde discrepancias) — se inyectan en cada prompt L3.
- `data/prompts/reglas_discriminantes.yaml` — guía experta por subsector confuso
  (hoy TRANSPORTE URBANO), inyectada como contexto de MÁXIMA prioridad en L3.

Eval contra etiquetado manual: `evaluation.py` / `load_expost_manual()` sobre
`data/raw/informe_expost.duckdb` (golden derivado en `data/golden/`).

## No romper

- **EBI_CODIGO sin dígito verificador** al publicar (D-6) o el JOIN con EBI da 0
  filas (lo protege `test_bip_code_normalized_for_join`).
- ⚠️ **Publish parcial:** publicar con `--limit` marca el resto
  `_present_in_latest=false`; el CLI advierte y pide confirmación. Pilotos → `--dry-run`.
- El LLM L3 va por `sni_commons.llm` (`SniCommonsLLMClient`; PT-4/PT-16).
- `store_publish.py` proyecta al `ENR_TIPO_PROYECTO_CONTRACT` y hace upsert **no
  destructivo** con `writer=` (ledger v1.1) — no escribir al store por otra vía.
