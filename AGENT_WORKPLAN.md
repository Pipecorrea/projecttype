# AGENT_WORKPLAN — ProyectType

> **Contexto obligatorio:** lee primero **`ECOSISTEMA.md`** (mapa del ecosistema +
> tu rol) y `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md` (estado vivo).
>
> **Estado:** **enriquecedor** funcionando. Cliente LLM unificado en sni-commons
> (PT-4). **Escribe `enr_tipo_proyecto` al store** (PT-5):
> `src/proyecttype/store_publish.py` + `scripts/enrich_to_store.py`. py3.12.
> 52 tests (unittest). Cascada L1 (keywords) → L2 (embeddings) → L3 (LLM).

## Verde antes de commitear
`uv run python -m unittest discover -s tests` (52; filtra el ruido "Could not
determine dtype" — benigno, de un xlsx ancho) · `uv run --with ruff ruff check src scripts tests`.

---

# PENDIENTES (orden sugerido)

## [PT-6] Pipeline directo store→store (sin CSV intermedio) — medio
Hoy: clasificar → CSV de resultados → `enrich_to_store.py` → store. Idealmente
ProyectType debería **leer los proyectos del store** (`read_pandas("CONSULTAS_EBI")`)
en vez de `data/raw/base_datos_extracto.csv`, clasificar, y escribir
`enr_tipo_proyecto` — todo contra el store, sin CSV locales.
- **Pasos:** loader que arme el input de la cascada desde `read_pandas("CONSULTAS_EBI")`
  (mapear columnas EBI → sector/subsector/nombre/descripción que espera L1).
- **Done-cuando:** `proyecttype enrich --from-store` clasifica leyendo del store y
  publica `enr_tipo_proyecto`, sin tocar `data/raw`.

## [PT-7] Re-clasificación incremental — bajo
`upsert_dataframe` ya es no destructivo. Clasificar solo los BIP nuevos/sin tipo
(no los 9k cada vez), usando el `l3_cache` + `read_pandas("enr_tipo_proyecto")` para
saber qué ya está clasificado con la versión actual del enricher.
- **Done-cuando:** `enrich --incremental` salta BIP ya clasificados.

## [PT-8] Migrar tests a pytest — bajo
Los tests usan `unittest` con `sys.path` hacks. Migrar a pytest (ya hay
`[tool.pytest.ini_options]`) homogeneiza con el ecosistema.
- **Done-cuando:** `uv run pytest` corre la suite; sin `sys.path.insert`.

---
## Notas (NO regresar)
- El código BIP en el store es canónico **SIN** dígito verificador (`store_publish`
  ya normaliza quitando `-N`; test `test_bip_code_normalized_for_join` lo protege).
- "ciclovía" NO es un tipo de la taxonomía actual (sí JARDIN INFANTIL, RUTA, PUENTE
  URBANO, etc.). Añadir tipos = editar `data/taxonomy/taxonomia_tipos_proyecto.yaml`,
  no el pipeline.
- SNI ya **consume** `enr_tipo_proyecto` (SNI-12, `--filter tipo_proyecto=<id|nombre>`):
  el atributo que publicas aquí ya es filtrable aguas abajo.

## Hecho (log)
PT-1/2 (Fase 0: git + N+1 eliminado en la cascada), PT-4 (cliente LLM → sni-commons),
**PT-5** (escribe `enr_tipo_proyecto` al store; JOIN con EBI 14.806 matches; bug del
dígito verificador atrapado con datos reales, commit f941fb5).
