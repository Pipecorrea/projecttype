---
tipo: evaluacion
ambito: ProjectType
actualizado: 2026-07-09
---

# ProjectType — diagnóstico y plan SOTA (2026-07)

> Espejo estructural de `OBSRATE/DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`. Master de
> tickets PT-15…PT-22 y SC-17 (commons). Los specs completos viven aquí; el
> [[AGENT_WORKPLAN]] resume estado y punteros.

---

## §0 · Método y alcance

**Provenance.** Revisión estratégica 2026-07-09 sobre el código en disco — **no** los
docs del repo (desactualizados: conteos 56/63 vs 72 tests reales; PT-7/PT-14 hechos
en código pero workplan pendiente). Commits locales sin push al inicio de la sesión:
`4710323` (rename ProyectType→ProjectType), `56fa548` (CLAUDE.md). Decisión de
convergencia con OBSRATE + UI HITL registrada como [[DECISIONES#D-19 · ProjectType gana loop humano propio (UI de validación/clasificación manual)|D-19]].

**Método.** Exploración de código (3 agentes) + verificación directa del agente
documentador. Inventario: **30 módulos**, **5.179 LOC** en `src/projecttype/`,
**72 tests** en **15 archivos** (`grep -r "def test_" tests/`). Perfil de
`data/raw/informe_expost.duckdb` (tabla `ex_post`, gitignored D-11) verificado con
DuckDB local.

**Alcance de este documento.** Diagnóstico + plan de trabajo (tickets PT-15…PT-22,
SC-17/SC-18). **No** incluye ejecución de código — esas tareas corren en ramas
dedicadas según [[AGENT_WORKPLAN]].

**Fuera de alcance.** Reportería/análisis aguas abajo (SNI Intelligence); editor de
catálogo/prompts en v1 (PT-22, v2); extracción prematura a commons (SC-18).

---

## §1 · Resumen ejecutivo

ProjectType es un enriquecedor costo-consciente (cascada L1→L2→L3) con ciclo
store→store funcionando, pero **tres brechas ejecutivas** impiden declararlo SOTA:

1. **Calidad no demostrable.** El golden formal tiene n=12 (fixture); la submuestra
   real (`Submuestra_tp.xlsx`) no está en disco. Los umbrales CI (0,798/0,656) fueron
   calibrados para otra muestra. Bugs P0 (`modelo` hardcodeado, caché L3 ciego a
   `prompt_version`) invalidan la trazabilidad que PT-9 prometió cerrar.

2. **Humano fuera del loop.** OBSRATE ya tiene HITL (editor de cortes, veredictos,
   SPA React). ProjectType publica etiquetas sin revisión humana ni cola de
   validación — imposible escalar con confianza sobre 326 tipos.

3. **El repo cuenta otra historia.** ~900 LOC muertas, docs stale, PT-7/PT-14 hechos
   sin reflejar en workplan, 2 commits sin push, `docs/eval/` sin commitear.

**Decisión D-19:** ProjectType gana **UI HITL local** (FastAPI + React, patrón
OBSRATE) para validar/clasificar manualmente — herramienta interna del enriquecedor,
no reportería. Publish al store **solo** vía `store_publish` + gate (D-13 intacto).

---

## §2 · Diagnóstico del estado actual

### P0 — Bugs verificados

| ID | Severidad | Hallazgo | Evidencia |
|---|---|---|---|
| B1 | **P0** | Fuga de `modelo` en producción | `cli.py:153-158` llama `classify_cascade_dataframe` sin `l3_model` → `pipeline_cascade.py:342` (`if l3_model:`) nunca agrega `_modelo_l3`; `:174` etiqueta caché con fallback `"gemini-2.5-flash"`. Filas L3 publican `modelo="n/a"`. **Nota:** `classify_cascade_csv()` (`pipeline_cascade.py:376-388`) SÍ resuelve `l3_model` vía `l3_config.llm.resolved_model()` — patrón a mover al pipeline. |
| B2 | **P0** | Caché L3 ciego a `prompt_version` | `l3_cache.py:83` valida solo `cache_version`+`model`. Cambio de prompt reutiliza respuestas viejas en silencio (existe `l3_cache_v2.jsonl` huérfano). |
| B3 | **P0→resuelto insumo** | Golden no reproducible | `Submuestra_tp.xlsx` ausente. **Insumo entregado 2026-07-09:** `data/raw/informe_expost.duckdb` (ver perfil abajo). |

### Deuda / simplificación (~900 LOC)

- Clientes LLM legacy `GeminiClient`/`OpenAIClient` (~250-300 LOC, sin tests;
  conservar `SniCommonsLLMClient`/`MockLLMClient`).
- `scripts/enrich_taxonomy_legacy.py` (323 LOC).
- Taxonomía triplicada tracked (yaml+csv+json; solo se lee YAML).
- `requirements.txt` divergente del pyproject.
- `_pick_column` duplicado ×3 (`evaluation.py`, `few_shot_mining.py`,
  `scripts/convert_submuestra_to_golden.py`).
- Dos cachés L3 (`l3_cache.jsonl` 218 entradas + huérfano `l3_cache_v2.jsonl` 293;
  total 511, gitignored en `data/output/`).
- `docs/estructura_proyecto.md` predata el pivote ("Ollama default" falso).
- Defaults rotos (`paths.py:18` → CSV inexistente, PT-12).
- `docs/eval/` untracked (17 archivos).
- Conteos stale en docs (56/63 vs 72 reales).
- Sin `test_classifier_l2.py` (único classifier sin test propio).
- `evaluation.py` / `few_shot_mining.py` siguen apuntando a `Submuestra_tp.xlsx`
  (`test_few_shot_mining.py:41` se auto-skipea).

### Convergencia con OBSRATE (gaps)

| Capacidad OBSRATE | ProjectType | Ticket |
|---|---|---|
| Gate de publicación (`store_gate.py`) | Ausente | PT-18 |
| Base HITL (`review/hitl_base.py` `JsonlHitlStore[T]`) | Ausente | PT-19 |
| SPA React (Vite + TanStack) | Ausente | PT-20 |
| Golden real formalizado | Fixture n=12 | PT-17 |
| Config-router con git write-through | N/A v1 | PT-22 (v2) |

**Ya converge vía commons:** `llm`, `contracts`, `store`, `eval` (SC-13/SC-14).

**Precedente SC-17:** en `sni_commons/contracts/sources.py`, los contratos
`enr_observaciones_grounding` y `enr_observaciones_etiquetas` YA tienen
`validado_por_humano`/`revisor` como recommended. `SCHEMA_VERSION` vigente = `1.3.0`.

**Inventario OBSRATE a replicar (rutas verificadas 2026-07-09):**

- `src/obsrate/store_gate.py`: `ResultadoGate`, `StoreGateRejectedError`,
  `validar_fila_<tabla>`, `aplicar_gate`, `aplicar_gate_o_abortar`,
  `formatear_resumen_gate`. Integración en `publish_to_store()` ANTES de upsert;
  CLI expone `--allow-rejected`.
- `src/obsrate/review/hitl_base.py`: `JsonlHitlStore[T]` genérico +
  `normalize_text`. Veredictos en `review/schemas.py`; stores en `review/hitl_stores.py`.
- `src/obsrate/api/`: `create_app()`, `mount_spa` en `api/static.py`
  (`/assets` + fallback SPA, excluye `/api/*`). Puertos: serve **8777**, Vite dev **5175**.
- `web/`: React 18.3, Vite 5.4, TS 5.6, TanStack Router 1.168 + Query 5.99,
  Tailwind 4.2, shadcn. CI job `web` bloqueante.
- Config-router (PT-22): `api/routers/config.py` + `config_prompts.py` con
  `_git_write_through()` — **ya implementado** en OBSRATE.
- **OJO:** `rate serve` NO tiene `--enable-publish` — en OBSRATE el publish va
  solo por CLI. El `--enable-publish` de PT-21 es **diseño NUEVO** de ProjectType
  (evita round-trip UI→export→CLI para veredictos validados).
- OBS-40 (SQLite multi-reviewer, hasta 5 revisores) vive en el DIAGNOSTICO de
  OBSRATE (~línea 609), no en su workplan — heredar si se suma equipo.

### Perfil de `data/raw/informe_expost.duckdb`

Tabla única `ex_post`, **2.357 filas**, gitignored (`data/raw/`, D-11).

| Dimensión | Valor |
|---|---|
| `codigo_bip` | Sin nulos ni duplicados; **TODOS con dígito verificador** (`30039296-0`) → conversor normaliza a canónico D-6 |
| `tipo_proyecto` | Completa (0 nulos), 168 tipos distintos |
| Sectores / subsectores | 14 sectores; **47 de 84** subsectores de la taxonomía |
| Años eval ex post | 2014–2025 |
| Columnas usadas | `codigo_bip`, `sector`, `subsector`, `nombre`, `justificación_proyecto`, `descripción` (2 nulos), `descriptor_1..3` + ~250 cols ignoradas |
| Match taxonomía | **98,3%** exacto normalizado (2.318/2.357) |
| Alias pendientes | **6 rótulos** (39 filas): ver tabla abajo |

**Mapa de aliases (conversor PT-17, NO tocar YAML — cambia `taxonomy_hash`):**

| Rótulo en duckdb | Tipo canónico | n |
|---|---|---|
| `Gimnasio Estandar` | `GIMNASIO ESTANDARD` | 19 |
| `Casetas Sanitarias/alcantarillado/agua Potable/energia` | `CASETAS SANITARIAS /ALCANTARILLADO/AGUA POTABLE/ENERGIA` | 13 |
| `Centro Cumplimiento Penitenciario (ccp)` | `CENTRO DE CUMPLIMIENTO PENITENCIARIO (CCP)` | 2 |
| 3 rótulos aeroportuarios con prefijo `Pequeño Aeródromo`/`Red Secundaria` | **Decisión 👤** — ¿alias al tipo sin prefijo o `sin_tipo_aplicable`? Resolver por subsector | 5 |

Tamaño estimado golden YAML: ~2,4 MB (≈1.000 chars/caso × 2.357) — commiteable;
alternativa JSONL o partición por sector.

---

## §3 · Definición operativa de SOTA

ProjectType SOTA = enriquecedor que:

1. **Demuestra calidad** — golden real n≈2.357 commiteado, gate CI sobre estrato
   `expost`, umbrales recalibrados y versionados; bugs P0 cerrados.
2. **Cierra el loop humano** — UI HITL local (validar propuestas L1/L2/L3,
   clasificar manual subsectores sin cobertura, exportar a golden, publicar con gate).
3. **Publica con procedencia auditable** — metadatos SC-13 completos (incl.
   `modelo` real), gate pre-upsert, guard anti-pisada de filas humano-validadas.
4. **Se mantiene solo** — incremental (PT-7 ✅), selección desde SNI (PT-14 ✅),
   escala por tramos con presupuesto (PT-13, gated).
5. **Cuenta la misma historia que el código** — docs al día, deuda muerta eliminada,
   taxonomía YAML SSOT (edición confinada a PT-22).

---

## §4 · Plan de trabajo

### Regla transversal

**PROHIBIDO tocar `data/taxonomy/taxonomia_tipos_proyecto.yaml` fuera de PT-22**
— cualquier cambio altera `taxonomy_hash` e invalida incremental + caché + store.

### [PT-15] Fuga `modelo` + caché prompt-aware — **S-M, P0**

**Objetivo.** Cada fila L3 publicada lleva el id real del modelo; el caché L3
invalida entradas cuando cambia el prompt, no solo el modelo.

**Cambios:**
- Resolver `l3_model` **dentro** de `classify_cascade_dataframe` (replicar patrón de
  `classify_cascade_csv()` con `l3_config.llm.resolved_model()`).
- Eliminar fallback hardcodeado `"gemini-2.5-flash"` en etiquetado de caché.
- Emitir `_modelo_l3` siempre cuando L3 está activo.
- `L3CacheEntry` gana campo `prompt_version`; `get()` exige triple match
  (`cache_version` + `model` + `prompt_version`).
- `L3_CACHE_VERSION` `"1"→"2"` (invalida 511 entradas locales: 218 +
  293 huérfanas — deliberado).
- Bump enricher `0.1.0→0.2.0`.

**Done-cuando (métricas verificables):**
- Test: filas L3 publicadas llevan `modelo` = id real del stub/config, no `"n/a"`.
- Test: cache-miss cuando `prompt_version` difiere con mismo BIP+modelo.
- `grep -r "gemini-2.5-flash" src/` → 0 ocurrencias en código de producción.
- `uv run pytest` verde; CI bloqueante.

---

### [PT-16] Saneo / simplificación — **M**

**Objetivo.** Eliminar ~900 LOC muertas y consolidar utilidades sin alterar
comportamiento del clasificador ni `taxonomy_hash`.

**Cambios:**
- Borrar: `GeminiClient`/`OpenAIClient` en `llm_client.py`; dep `openai` del pyproject;
  `scripts/enrich_taxonomy_legacy.py`; `requirements.txt`; taxonomía csv/json tracked
  (`data/taxonomy/taxonomia_tipos_proyecto.{csv,json}` — el `.xlsx` y
  `embeddings_cache/` untracked no se tocan; `colisiones_keyword.csv`/`composites_index.csv`
  quedan); `docs/estructura_proyecto.md`.
- Consolidar `_pick_column` (×3) en `text_utils`.
- Caché único L3 (resolver huérfano v2).
- Commitear `docs/eval/` (17 archivos untracked).
- Añadir `test_classifier_l2.py`.
- Re-apuntar `evaluation.py`/`few_shot_mining.py` al duckdb o marcarlos legacy;
  `DEFAULT_SUBMUESTRA` en `paths.py` → `DEFAULT_EXPOST_DB`.
- Conteos docs al día.

**Done-cuando (métricas verificables):**
- `grep -r "GeminiClient\|OpenAIClient\|enrich_taxonomy_legacy" src/ scripts/` → 0.
- `grep -r "_pick_column" src/` → 0 (solo `text_utils`).
- `uv run pytest` ≥ **76** passed.
- `taxonomy_hash` idéntico antes/después (test o diff manual).
- `uv run ruff check` + `uv run mypy src` → 0.

---

### [PT-17] Golden real (absorbe PT-10) — **M, insumo 👤 entregado**

**Objetivo.** Golden commiteado derivado de `informe_expost.duckdb` (n=2.357),
gate CI sobre estrato `expost`, umbrales recalibrados.

**Cambios:**
- Reescribir `scripts/convert_submuestra_to_golden.py` →
  `convert_expost_to_golden.py`: lee duckdb, normaliza `codigo_bip` (D-6), aplica
  mapa de aliases (6 rótulos), tags `expost` + `subsector:<X>` + `ano_eval:<YYYY>`.
- Golden completo reemplaza fixture n=12 en `data/golden/golden_tipo_proyecto.yaml`
  (fixture → `tests/fixtures/`; formato YAML ~2,4 MB o JSONL — decidir en ticket).
- Métricas por estrato; **gate solo sobre estrato `expost`**.
- Recalibrar `data/golden/umbrales.yaml` al medido (decisión 👤 en DECISIONES).
- `docs/eval/golden_cobertura_subsector.csv` (47/84 subsectores — insumo UI
  "sin cobertura").
- CI evalúa golden commiteado (derivado); conversión es local (duckdb no viaja).

**Done-cuando (métricas verificables):**
- `uv run python scripts/eval_golden.py --ci` verde con golden n≈2.357.
- Baseline reproducido desde clone limpio anotado en `docs/eval/`.
- Test de degradación (mutar umbral scorer) pone gate rojo.
- Fixture n=12 movido a `tests/fixtures/` y referenciado solo en tests unitarios.

---

### [SC-17] Contrato HITL en commons — **S**

**Objetivo.** `ENR_TIPO_PROYECTO_CONTRACT` gana campos HITL recommended, alineado
con `enr_observaciones_grounding`/`enr_observaciones_etiquetas`.

**Cambios:**
- `contracts/sources.py`: añadir `validado_por_humano`/`revisor` (recommended).
- `SCHEMA_VERSION` `1.3.0→1.4.0`, entrada CHANGELOG.

**Done-cuando (métricas verificables):**
- Test round-trip contrato con columnas HITL.
- `uv run pytest` en sni-commons verde; consumidores sin regresión.
- PT-21 puede validar df con contrato actualizado.

*(Spec corta también en `sni-commons/AGENT_WORKPLAN.md`.)*

---

### [PT-18] Gate de publicación + re-publish (absorbe PT-9 re-publish y PT-11 guard) — **M + 👤**

**Objetivo.** Ninguna fila inválida entra al store; re-publish real con metadatos
completos cierra la deuda PT-9/PT-11.

**Cambios:**
- Réplica de `OBSRATE/src/obsrate/store_gate.py` (mismos símbolos; una tabla):
  motivos `clave_no_canonica`, `tipo_fuera_de_taxonomia`, metadatos ausentes,
  `nivel_asignacion` inválido (∉{L1,L2,L3,humano}), evidencia>500,
  `revisor_ausente_con_validacion`.
- `aplicar_gate_o_abortar(allow_rejected_pct=0)` en `publish_to_store` ANTES de
  upsert; flag CLI `--allow-rejected`.
- 👤 Re-publish `enrich --from-store --enable-l3` SIN `--incremental` (~500
  llamadas L3 re-pagadas por bump de caché PT-15).

**Done-cuando (métricas verificables):**
- Tests: fila con clave no canónica → rechazada; df limpio → pasa.
- Tras re-publish 👤: SQL PT-9 = 0 (`taxonomy_hash`/`prompt_version`/`modelo` poblados).
- SQL PT-11 = 0 (`EBI_CODIGO LIKE '%-%'` vigentes).
- Gate integrado en CI con stub.

---

### [PT-19] Backend HITL — **L**

**Objetivo.** API FastAPI read-only + stores JSONL para cola de revisión y
clasificación manual. Sin escrituras al store desde el server.

**Cambios:**
- `src/projecttype/review/`: `hitl_base.py` (adaptado de OBSRATE), `schemas.py`,
  `TipoReviewStore` (snapshot memoria: store read-only + CoT caché L3 + veredictos).
- `src/projecttype/api/`: `main.py` (`create_app()`), `static.py` (`mount_spa`),
  health `GET /api/health`, routers:
  - `/api/review/summary|queue|item/{ebi}|reload`
  - `/api/manual/subsectores|pendientes`
  - `/api/catalogo/arbol`
- CLI `projecttype serve`, puerto **8788** (`PROJECTTYPE_UI_PORT`); Vite dev **5176**
  con proxy `/api`→8788.
- Deps nuevas: `fastapi`, `uvicorn`.

**Modelo de datos HITL:** `data/review/veredictos_tipo.jsonl` **commiteado**
(política datos derivados).

`RevisionTipoRecord`: `ebi_codigo` (canónico D-6), contexto denormalizado,
`origen` (l1|l2|l3|manual), propuesta sistema + confianza + evidencia + CoT,
`veredicto` (aceptado|corregido|sin_tipo_aplicable|no_evaluable),
`tipo_final_*`, `notas`, `revisor`, `revisado_en`, snapshot era
(`taxonomy_hash`/`prompt_version`/`modelo`/`enricher_version`),
marcas `exportado_golden_en`/`publicado_en`. Último veredicto por EBI gana;
single-reviewer v1 (límite explícito; heredar SQLite OBS-40 si equipo crece).

**Done-cuando (métricas verificables):**
- `uv run projecttype serve` levanta API; `GET /api/health` → 200.
- Tests API con TestClient: cola, item, reload.
- **Dependencia dura:** re-publish 👤 PT-18 (sin columnas nuevas la cola está vacía).
- 0 escrituras al store desde endpoints en este ticket.

---

### [PT-20] SPA v1 — **L**

**Objetivo.** UI React para revisión y clasificación manual, clonada del stack OBSRATE.

**Cambios:**
- Scaffold `web/` — React 18.3, Vite 5.4, TS 5.6 strict, TanStack Router 1.168 +
  Query 5.99, Tailwind 4.2, shadcn.
- `/revision`: cola filtrable (origen/subsector/estado, confianza asc) + ficha
  (evidencia L1/L2 + CoT L3 colapsable) + acciones Aceptar/Corregir/Sin tipo
  aplicable/No evaluable + `revisor` obligatorio + atajos teclado.
- `/manual`: subsectores con badges cobertura → clasificar pendientes; picker
  jerárquico 326 tipos pre-filtrado al subsector (command palette, búsqueda
  normalizada, toggle catálogo completo).
- Header: frescura store (API SC-11) + `taxonomy_hash` + contadores.
- CI job `web` bloqueante: Node 20, `npm ci`, `npm run build`.

**Done-cuando (métricas verificables):**
- `npm run build` verde local y en CI.
- Smoke manual: flujo revisar 1 item + clasificar 1 pendiente persiste JSONL.
- Typecheck strict 0 errores.

---

### [PT-21] Loop de salida HITL — **M**

**Objetivo.** Veredictos humanos fluyen a golden y store con gate, sin pisar
validaciones previas.

**Cambios:**
- `hitl export-golden`: casos `caso_id="hitl-<ebi>"`, tags
  `hitl/origen:/veredicto:/subsector:`, skip-existing, marca `exportado_golden_en`.
- `hitl publish`: vía `store_publish`+gate, `mark_missing=False`, marca `publicado_en`.
- Endpoints publish solo con `serve --enable-publish` (opt-in, D-13) — **diseño
  nuevo** (OBSRATE no lo tiene; justificado: evita round-trip UI→CLI).
- Guard anti-pisada: `enrich` no pisa filas `validado_por_humano=true` (salvo
  `--override-human`); `filter_pending` excluye validados.
- Mapeo publicación: aceptado conserva nivel/confianza; corregido/manual →
  `nivel_asignacion="humano"`, confianza 1.0.

**Done-cuando (métricas verificables):**
- Test: veredicto exportado aparece en golden con tags correctos.
- Test: publish respeta gate; fila humana no se pisa en enrich incremental.
- Gate CI golden: estrato `hitl` reportado aparte (no contamina `expost`).

**Deps:** SC-17 + PT-18 + PT-19.

---

### [PT-22] v2 editor catálogo/prompts/few-shots — **L, DIFERIDA**

**Objetivo.** Edición gobernada de taxonomía YAML, prompts y few-shots con eval
obligatorio antes/después.

**Cambios:**
- Patrón config-router OBSRATE (`api/routers/config.py` + `config_prompts.py`,
  `_git_write_through()`, `data/config/prompt_versions.json`).
- Regla dura: guardar exige eval antes/después (endpoint dispara `--ci`, bloquea
  si gate cae).
- Insumo: veredictos `sin_tipo_aplicable` de PT-20/21.

**Done-cuando (métricas verificables):**
- Editar prompt → eval antes/después registrado; gate no cae.
- Editar taxonomía → `taxonomy_hash` nuevo documentado; re-clasificación selectiva
  documentada.

**Gated por:** PT-17 + PT-20.

---

### [SC-18] Extraer patrones duplicados a commons — **futuro, no bloquea**

**Objetivo.** Cuando PT y OBSRATE estabilicen `hitl_base`, `store_gate`, retry
patterns e ingest golden, extraer a sni-commons.

**Done-cuando:** ambos consumidores usan módulo commons; 0 duplicación verificada
con grep cross-repo.

---

## §5 · Gates y umbrales consolidados

| Gate | Umbral / regla | Cuándo |
|---|---|---|
| Golden L1+L2 precisión | Baseline en `umbrales.yaml` (recalibrar PT-17 👤) | `eval_golden.py --ci` |
| Golden L1+L2 cobertura | Idem | Idem |
| Golden estrato | Gate **solo** `expost`; `hitl` reportado aparte | PT-17/PT-21 |
| Store publish | `allow_rejected_pct=0` default | PT-18 |
| Clave EBI | Canónica sin DV (D-6) | PT-18 guard |
| Evidencia | ≤ 500 chars | Contrato SC-13 |
| Taxonomía | Sin edits fuera PT-22 | Regla transversal |
| Caché L3 | Triple match version+model+prompt | PT-15 |
| Humano | `validado_por_humano=true` no se pisa | PT-21 |

Umbrales vigentes (fixture n=12, **obsoletos** hasta PT-17):
`precision_l1_l2: 0.798`, `cobertura_l1_l2: 0.656`.

---

## §6 · Secuencia y dependencias

```
Arranque paralelo:
  PT-15 (P0 bugs)  +  SC-17 (contrato)  +  PT-12 (rutas)  +  PT-17 (golden)  +  👤 push commits 4710323/56fa548

PT-15 ──→ PT-16 (mismo terreno pipeline/caché)
PT-17 ──→ PT-22 (gated)
SC-17 ──→ PT-21

PT-16 ──→ PT-18 (gate + re-publish)
         └── 👤 re-publish ~500 L3
              └── PT-19 (backend HITL — cola necesita columnas nuevas)
                   └── PT-20 (SPA)
                        └── PT-21 (loop salida)
                             └── PT-22 (v2 editor, gated)

PT-13 (escala 👤) — GATED por PT-15 + PT-17 + PT-18(re-publish); recomendado tras PT-20
```

**Ruta crítica:** PT-15 → PT-18 → re-publish 👤 → PT-19 → PT-20 → PT-21.

**Hazards:**

| Riesgo | Mitigación |
|---|---|
| Golden contaminado por auto-confirmación | Gate CI solo estrato `expost`; `hitl` aparte |
| Enrich pisa validaciones humanas | Guard anti-pisada PT-21 |
| Divergencia golden↔store | Ambas salidas del mismo JSONL + query consistencia |
| Single-writer D-13 | Snapshot memoria + `/reload` + publish opt-in |
| `taxonomy_hash` hiperfrágil | Edición taxonomía solo PT-22 |
| Invalidación caché ~500 LLM | Presupuestar 👤 antes de re-publish |
| Pantalla vacía si PT-19 antes de re-publish | Secuencia dura PT-18→PT-19 |
| Colisión puertos | PT 8788/5176 vs OBS 8777/5175 |

---

## §7 · Decisiones que requieren a Felipe 👤

| # | Decisión | Estado |
|---|---|---|
| 1 | Entrega golden (`Submuestra_tp.xlsx`) | **SUPERADA** — duckdb entregado 2026-07-09 |
| 2 | Mapeo 3 rótulos aeroportuarios con prefijo | **Pendiente** — alias sin prefijo vs `sin_tipo_aplicable` vs subsector |
| 3 | OK re-pago ~500 llamadas L3 (re-publish PT-18) | **Pendiente** |
| 4 | Nuevos umbrales tras baseline n=2.357 | **Pendiente** — registrar en DECISIONES |
| 5 | Push commits `4710323`, `56fa548` | **Pendiente** |
| 6 | Usar o no `--enable-publish` en producción | **Pendiente** — opt-in diseñado |
| 7 | Presupuesto PT-13 (escala cartera) | **Pendiente** — gated |

---

## §8 · Mapeo con AGENT_WORKPLAN.md

| Ticket | Workplan | Estado doc |
|---|---|---|
| PT-7 | [[AGENT_WORKPLAN#PT-7]] | ✅ HECHO `242af99` |
| PT-9 metadatos | [[AGENT_WORKPLAN#PT-9]] | ✅ código; re-publish → PT-18 |
| PT-10 golden | [[AGENT_WORKPLAN#PT-10]] | 🟡 → **PT-17** |
| PT-11 guard fósil | [[AGENT_WORKPLAN#PT-11]] | Parcial → **PT-18** |
| PT-12 rutas | [[AGENT_WORKPLAN#PT-12]] | Pendiente |
| PT-13 escala | [[AGENT_WORKPLAN#PT-13]] | Gated (re-mapeado) |
| PT-14 selección | [[AGENT_WORKPLAN#PT-14]] | ✅ HECHO `3200751` |
| PT-15…PT-22 | [[AGENT_WORKPLAN#PLAN SOTA 2026-07]] | Spec completa **aquí** |
| SC-17 | `sni-commons/AGENT_WORKPLAN.md` | Pendiente |
| D-19 | [[DECISIONES#D-19]] | ✅ 2026-07-09 |

**Absorciones:** PT-9 (re-publish) → PT-18 · PT-10 → PT-17 · PT-11 (guard) → PT-18.
