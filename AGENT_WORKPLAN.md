# AGENT_WORKPLAN — ProyectType

> **Autocontenido para un agente que trabaja en este repo.** Contexto completo y ADRs: `/Users/felipecorrea/Vs/PLAN_ECOSISTEMA.md`.
> Ejecuta **al pie de la letra**. Ambigüedad → **detente y pregunta**. Fuera de alcance → `HALLAZGOS_AGENTE.md`.

## Contexto mínimo
ProyectType debe convertirse en un **servicio de enriquecimiento**: clasifica el **tipo de proyecto** (atributo que NO existe en EBI/RATE — ej: "ciclovía") y lo **escribe de vuelta al store común** como `enr_tipo_proyecto`, para que SNI Intelligence pueda filtrar por ese atributo. Hoy es el repo menos empaquetado (sin `pyproject.toml`, sin lock, tests en `unittest`) pese a tener una cascada L1/L2/L3 valiosa.

## Definición de Done (toda tarea)
1. `ruff`/`format` limpios · 2. `mypy` sin nuevos errores · 3. tests verdes + test nuevo si cambia comportamiento · 4. no romper la CLI de `scripts/` sin nota · 5. commit atómico con `Co-Authored-By` · 6. bump si tocas contratos · 7. fuera de alcance → `HALLAZGOS_AGENTE.md`.

---

## Tareas de este repo

### [PT-1] `pyproject.toml` + lock + `git init` — 🐛 **alto** — Fase 0 — [P]
- **Problema:** sin `pyproject.toml`, sin lock (era decisión explícita "install manually"), tests `unittest` con `sys.path` hacks.
- **Pasos:** 1) crear `pyproject.toml` (uv, `requires-python>=3.12`), portar `requirements.txt`; 2) `uv lock`; 3) `git init` + `.gitignore` (`data/`, caches, `.venv/`); 4) (opcional pero recomendado) migrar tests a pytest sin `sys.path` hacks.
- **Done-cuando:** `uv sync && uv run pytest` verde; repo inicializado.

### [PT-2] Arreglar N+1 en cascada L3 — 🐛 medio (perf) — Fase 0 — [P]
- **Problema:** `src/proyecttype/pipeline_cascade.py:174` filtra todo el DataFrame por cada candidato (`with_l1.filter(pl.col("_row_idx")==idx).to_dicts()[0]`) ⇒ cuadrático.
- **Pasos:** construir `rows_by_idx = {r["_row_idx"]: r for r in with_l1.to_dicts()}` una vez antes del loop; usarlo en `:174` y patrones similares.
- **Done-cuando:** sin filtro-en-loop; resultados idénticos en test de regresión sobre CSV de muestra.

### [PT-3] Paralelizar L3 respetando rate-limit — 💡 bajo (perf) — Fase 3 — [P]
- **Problema:** `pipeline_cascade.py:208-251` llama al LLM fila a fila.
- **Pasos:** pool acotado con throttle (reusar `sni_commons.llm`); preservar orden y caché L3.
- **Done-cuando:** lote grande más rápido sin exceder RPM; caché intacta.

### [PT-4] Adoptar `sni-commons.llm` — 💡 medio — Fase 1 — [B] (dep: SC-1)
- **Problema:** `llm_client.py` (urllib; GeminiClient/OpenAIClient/OllamaClient + Mock) es otra de las 4 implementaciones.
- **Pasos:** reemplazar por `sni_commons.llm`; conservar un mock para tests.
- **Done-cuando:** sin cliente LLM propio; tests L3 (mock) verdes.

### [PT-5] Convertir ProyectType en servicio de enriquecimiento (write-back) — 💡 alto — Fase 3 — [B] (dep: ST-1)
- **Problema (caso "ciclovía"):** el tipo de proyecto no existe en EBI/RATE; ProyectType lo crea y debe escribirlo al store.
- **Pasos:** 1) leer proyectos desde el store; 2) escribir `enr_tipo_proyecto` (clave `EBI_CODIGO` + `enricher_version`; columnas `tipo_final_id/nombre`, `score`, `nivel`); 3) CLI `proyecttype enrich --to-store`.
- **Done-cuando:** `enr_tipo_proyecto` poblado e idempotente; SNI puede filtrar por tipo (`[SNI-13]`).

---

## Dependencias cruzadas (otros repos)
- `PT-4` depende de `SC-1` · `PT-5` depende de `ST-1` → repo **BIP CD**.
- `PT-5` habilita `[SNI-4]` y `[SNI-13]` (SNI consume el tipo de proyecto en vez de reimplementarlo).
- ADR-3 (servicios de enriquecimiento) aplica aquí.
