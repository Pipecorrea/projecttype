# AGENT_WORKPLAN — ProyectType

> **Contexto obligatorio:** lee primero `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md`.
>
> **Estado:** ProyectType es un **enriquecedor** funcionando. Cliente LLM
> unificado en sni-commons (PT-4). **Escribe `enr_tipo_proyecto` al store (PT-5)**:
> `src/proyecttype/store_publish.py` + `scripts/enrich_to_store.py`. py3.12.
> 52 tests (unittest). Cascada L1 (keywords) → L2 (embeddings) → L3 (LLM).

## Verde antes de commitear
`uv run python -m unittest discover -s tests` (52, filtra el ruido
"Could not determine dtype" — es benigno, de un xlsx ancho) ·
`uv run --with ruff ruff check src scripts tests`.

---

## [PT-6] Pipeline directo store→store (sin CSV intermedio) — medio

Hoy el flujo es: clasificar → CSV de resultados → `enrich_to_store.py` → store.
Idealmente ProyectType debería **leer los proyectos del store** (`CONSULTAS_EBI`,
vía `read_pandas`) en vez de `data/raw/base_datos_extracto.csv`, clasificar, y
escribir `enr_tipo_proyecto` — todo contra el store, sin CSV locales.
- **Pasos:** loader que arme el input de la cascada desde `read_pandas("CONSULTAS_EBI")`
  (mapear columnas EBI → sector/subsector/nombre/descripción que espera L1).
- **Done-cuando:** `proyecttype enrich --from-store` clasifica leyendo del store y
  publica `enr_tipo_proyecto`, sin tocar `data/raw`.

## [PT-7] Re-clasificación incremental — bajo

`upsert_dataframe` ya es no destructivo (re-publicar solo actualiza tipos que
cambiaron). Aprovecharlo: clasificar solo los BIP nuevos/sin tipo en el store
(no los 9k cada vez). Usa el `l3_cache` existente + `read_pandas("enr_tipo_proyecto")`
para saber qué ya está clasificado.
- **Done-cuando:** `enrich --incremental` salta BIP ya clasificados con la versión
  actual del enricher.

## [PT-8] Empaquetado de tests a pytest — bajo
Los tests usan `unittest` con `sys.path` hacks. Migrar a pytest (ya hay
`[tool.pytest.ini_options]` en pyproject) homogeneiza con el resto del ecosistema.
- **Done-cuando:** `uv run pytest` corre la suite; quitar los `sys.path.insert`.

---
## Notas
- El código BIP en el store es canónico SIN dígito verificador (`store_publish`
  ya normaliza quitando `-N`). No regreses ese fix (test
  `test_bip_code_normalized_for_join` lo protege).
- "ciclovía" NO es un tipo de la taxonomía actual (sí JARDIN INFANTIL, RUTA,
  PUENTE URBANO, etc.). Añadir tipos es editar
  `data/taxonomy/taxonomia_tipos_proyecto.yaml`, no el pipeline.
