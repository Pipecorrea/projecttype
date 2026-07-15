---
tipo: workplan
ambito: ProjectType
actualizado: 2026-07-10
---

# AGENT_WORKPLAN — ProjectType

> **Contexto obligatorio:** lee primero **`ECOSISTEMA.md`** (mapa del ecosistema +
> tu rol) y `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md` (estado vivo). Rumbo:
> `/Users/felipecorrea/Vs/PROPUESTA_SOTA_2026-06.md` (los próximos pasos de este
> repo salen de ahí). Visión y alcance del repo: `VISION.md`.
>
> **Estado:** **enriquecedor** funcionando, ciclo **store→store completo** (PT-6):
> `projecttype enrich --from-store` lee CONSULTAS_EBI, clasifica y publica
> `enr_tipo_proyecto`. Cliente LLM unificado en sni-commons (PT-4). py3.12.
> **117 tests** (**pytest**, PT-8/9/10/14/15/16/17/18/19/23/24/25), mypy **--strict**,
> ruff limpio, golden real n=2.357 en gate CI. Cascada L1→L2→L3 + **UI HITL backend
> (PT-19): `projecttype serve`**. Diagnóstico SOTA: `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`.

## Verde antes de commitear
`uv run pytest` (117) · `uv run ruff check src scripts tests` · `uv run mypy src`
(--strict) · `uv run python scripts/eval_golden.py --ci` — **lo mismo que corre CI (bloqueante)**.

---

# HECHO RECIENTE (2026-06-26, consolidado a main)

- **Reglas discriminantes por subsector** (`data/prompts/reglas_discriminantes.yaml`
  + `prompt_context.guia_discriminante_for_subsector` + `l3.yaml`): guía de dominio
  curada para TRANSPORTE URBANO (el cuello de botella del baseline, 11 tipos casi
  indistinguibles), inyectada como `contexto_adicional` de máxima prioridad en L3.
  Mejora medida en corrida local sobre las 424 filas: cobertura 30→80 %, precisión
  35→56 %. ⚠️ Evidencia **no reproducible en CI** (artefacto local `data/output/`);
  formalizar como golden-set (§4.1/R3) antes de declarar resuelto el subsector. n=1
  subsector — no extrapolar el +21 pp al resto de la taxonomía.
- **Resiliencia L3** (`pipeline_cascade` + `MockLLMClient.fail_on_calls` + test
  `test_pipeline_cascade_l3_resilience`): un 503/429 transitorio de una fila ya no
  aborta el lote — se marca residual, se sigue y se reporta; el caché permite reanudar.

---

# PENDIENTES (orden sugerido)

> ✅ **Deuda de commits saldada (2026-07-10):** PT-15/16/17/18/23/24 (~90 archivos,
> golden n=2.357, `store_gate.py`, `llm/provider.py`, caché Vertex) estaban solo
> en el working tree desde el commit PT-14 (`3200751`); ahora en 3 commits
> coherentes: `7f776b1` (PT-15/16/24 — cascada L3, transporte LLM, saneo),
> `5f7f2e3` (PT-17/23 — golden real + holdout + caché Vertex), `d9ccc3f`
> (PT-18 — gate de publicación). Verde CI-completo verificado antes y después de
> comitear (pytest 105 · ruff 0 · mypy --strict 0 · `eval_golden --ci` aprobado).

# ⭐ PLAN 2026-07 — lo que ordena la evaluación estratégica (creado 2026-07-02)

> Master de referencia: `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md` (specs completas PT-15…PT-22).
> Reconcilia `/Vs/EVALUACION_ESTRATEGICA_2026-07.md` §8.4 → §9.11.
> Absorciones: PT-9 (re-publish) → **PT-18** · PT-10 → **PT-17** · PT-11 (guard) → **PT-18**.

> **Origen:** `/Vs/EVALUACION_ESTRATEGICA_2026-07.md` (§3 score 560, §4.1, §5.1 filas 1/6/9, §5.2-A/B).
> **Los tres hallazgos que ordenan el plan:** (1) la trazabilidad rica (evidencia L1,
> CoT L3, modelo) muere en CSVs locales gitignored — el store recibe 6 columnas peladas;
> (2) cobertura 1,3% de la cartera vigente (2.331 de ~184.260) y el store guarda el
> fósil del bug PT-5 (mitad de las claves huérfanas con formato viejo); (3) el golden
> (Submuestra_tp.xlsx) ni siquiera está en el repo — ninguna mejora es medible.
> **Regla del plan (anti-objetivo §5.3): NO re-clasificar la cartera completa antes de
> PT-9 + PT-10** — sería pagar LLM para producir filas no auditables que habría que regenerar.
> **Implementación por agentes Cursor:** no improvisar fuera de estas especificaciones;
> ante ambigüedad, detenerse y preguntar en el PR, no adivinar.

#### 🔒 Estándar de cumplimiento (todas las tareas PT-9…PT-13)

1. **Verde igual a CI antes de cada commit:** `uv run pytest` → 0 fallos ·
   `uv run ruff check src scripts tests` → 0 · `uv run mypy src` → `--strict`, 0.
2. **Cobertura de cada módulo nuevo ≥ 90%.** Cada función pura → unit test con casos
   adversarios; cada schema → round-trip.
3. **Reglas de casa:** LLM solo vía `sni_commons.llm` (adaptador PT-4); EBI_CODIGO al
   store SIEMPRE sin dígito verificador (D-6; usar `to_store_key` de commons cuando
   exista SC-12); publish al store SIEMPRE vía `store_publish.py` + contrato.
4. **Una tarea por rama** (`pt-9-metadatos`, …). Ningún "hecho" sin pegar la salida
   real del comando de verificación en el log.
5. **Toda corrida con LLM pagado la dispara el dueño (👤)** — el agente deja el
   comando listo y probado con `--dry-run`/stub.

#### Secuencia (plan SOTA 2026-07 — ver DIAGNOSTICO §6)

```
Paralelo: PT-15 + SC-17 + PT-12 + PT-17 + 👤 push
PT-15 → PT-16 → PT-18 → PT-23 👤 eval holdout → PT-19 → PT-20 → PT-21 → 👤 publish
PT-13 (escala 👤) — GATED por PT-15+PT-17+PT-18; recomendado tras PT-20
PT-22 (editor v2) — GATED por PT-17+PT-20
```

**Regla:** no tocar `data/taxonomy/taxonomia_tipos_proyecto.yaml` fuera de **PT-22**
(cualquier cambio altera `taxonomy_hash`).

#### [PT-9] Metadatos de inferencia en `enr_tipo_proyecto` — **HECHO 2026-07-02 (✅ verificado; falta el re-publish real 👤 — el store aún no tiene las columnas, la query SQL de cumplimiento queda pendiente)**

**Objetivo.** Cada fila publicada lleva su procedencia completa. Es el patrón que el
contrato de OBSRATE ya modela — copiarlo, no inventarlo (evaluación §5.2-A).

**Cambios:**
- `store_publish.py`: proyectar y publicar las columnas nuevas del contrato SC-13:
  - `nivel_asignacion`: `"L1" | "L2" | "L3" | "residual"`.
  - `confianza`: score del nivel que asignó (L1: score del scorer; L2: similitud
    coseno; L3: confianza del LLM; residual: NULL).
  - `evidencia_resumen` (≤ 500 chars): L1 → keywords ganadoras + score;
    L2 → vecino más cercano + similitud; L3 → resumen del razonamiento CoT
    (primeros 500 chars del campo que hoy muere en el CSV).
  - `modelo`: id real del modelo L3 (`"n/a"` para L1/L2).
  - `prompt_version`: sha256 corto (12 hex) del contenido concatenado de
    `data/prompts/l3.yaml` + `reglas_discriminantes.yaml` + few-shots — calculado
    en runtime, no hardcodeado.
  - `taxonomy_hash`: sha256 corto de `data/taxonomy/taxonomia_tipos_proyecto.yaml`.
  - `enricher_version`: ya existe — mantener.
- `pipeline_cascade`/`ClassifierCascade`: propagar la evidencia por nivel hasta el
  df final (hoy se pierde entre la cascada y el publish).

**Done-cuando (métricas verificables):**
- Tests: una corrida stub de 5 filas (una por nivel + residual) publica el df con
  TODAS las columnas pobladas según el nivel; `prompt_version` cambia si se edita
  un byte del YAML (test); `evidencia_resumen` nunca > 500 chars (test adversario
  con CoT largo); contrato SC-13 valida el df (o el shim local si SC-13 no llegó).
- Verificación en store tras el primer publish real (pegar en el log):
  ```sql
  SELECT count(*) FROM enr_tipo_proyecto
  WHERE _present_in_latest AND (taxonomy_hash IS NULL OR prompt_version IS NULL);  -- = 0
  ```

**Implementado:** `inference_metadata.py` + proyección en `store_publish.py` +
`_modelo_l3` en `pipeline_cascade.py`. Tests: `tests/test_inference_metadata.py` (4).

#### [PT-10] Golden-set EN el repo + gate en CI — **🟡 PARCIAL → absorbido por PT-17**

> Andamiaje completo (eval_golden, umbrales, CI). **Falta lo central:** golden n=12
> (fixture). Insumo 👤 entregado 2026-07-09: `data/raw/informe_expost.duckdb`
> (n=2.357). Spec completa en `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md` §4 PT-17.

#### [PT-7] Re-clasificación incremental REAL — **✅ HECHO 2026-07-06 (`242af99`)**

**Objetivo.** Clasificar solo BIP nuevos/cambiados; publish parcial que NO marca el
resto como ausente.

**Implementado:** `enrich --from-store --incremental` — anti-join contra
`enr_tipo_proyecto` vigente por (`EBI_CODIGO`, `taxonomy_hash`, `enricher_version`,
`prompt_version`); publica con `mark_missing=False` (SC-13). Tests en
`tests/test_incremental.py` (4).

**Done-cuando:** ✅ tests verdes; CLI `--incremental --dry-run` imprime conteos.

#### [PT-11] Saneo del fósil PT-5 — **parcial; guard permanente → PT-18**

> Métrica principal cumplida (huérfanas vigentes = 0). Guard en `store_publish` y
> re-publish con metadatos → **PT-18** (absorbe PT-9 re-publish + PT-11 guard).

#### [PT-12] Rutas y entrada única (defaults rotos → store-first)

**Objetivo.** El camino de producción no depende de CSVs locales inexistentes
(evaluación: "defaults de rutas rotos").

**Cambios:**
- Auditar `config`/scripts: todo default que apunte a un archivo local inexistente
  se reemplaza por (a) el store como entrada por defecto (`BIP_DATA_DIR`), o
  (b) error claro al inicio ("falta X; pásalo con --input") — nunca un
  FileNotFoundError a mitad de corrida.
- El camino CSV queda SOLO para calibración/eval (documentarlo así en README y
  CLAUDE.md); los scripts de eval declaran sus inputs explícitos.

**Done-cuando:** en un clone limpio con solo `BIP_DATA_DIR` seteado,
`uv run projecttype enrich --from-store --dry-run --limit 5` funciona sin editar
nada; test de config para el error claro; `grep` de rutas hardcodeadas a
`data/output/...` en `src/` → 0 (quedan solo en `scripts/` de eval).

#### [PT-13] Escala a cartera vigente — por tramos, con presupuesto (👤 GATED)

**Objetivo.** Cobertura 1,3% → cartera vigente completa, SIN deuda inauditable.
**Bloqueada hasta cerrar PT-15 + PT-17 + PT-18 (re-publish). Recomendado tras PT-20**
(la UI valida cada tramo).

**Estrategia por tramos:**
1. L1+L2 (gratis, deterministas) sobre TODO el universo vigente → publica lo
   asignado con confianza; mide el residual real que iría a L3.
2. L3 por tramos priorizados (orden: subsectores con demanda de SNI; TRANSPORTE
   URBANO primero — ya tiene reglas discriminantes), con `BudgetTracker` de commons
   y tope de gasto por tramo definido por el dueño ANTES de correr.
3. Después de cada tramo: eval del golden por subsector si existe; registrar
   costo real + cobertura en `docs/eval/ESCALA_2026-07.md`.

**Done-cuando (por tramo, pegar salidas):**
- Cobertura: `SELECT count(*) FROM enr_tipo_proyecto WHERE _present_in_latest;`
  crece según lo planificado del tramo; % del universo vigente reportado.
- 100% de filas nuevas con metadatos PT-9 (query de PT-9 = 0).
- Costo real ≤ presupuesto del tramo (BudgetTracker output).

#### Métricas de éxito del repo (verificación al cerrar el plan)

| Métrica | Hoy | Objetivo | Verificación |
|---|---|---|---|
| Trazabilidad por fila publicada | 6 columnas peladas | procedencia completa (PT-9) | SQL PT-9 = 0 |
| Golden en repo + gate CI | fixture 12 casos (Submuestra pendiente) | gate bloqueante | job CI + eval --ci |
| Claves huérfanas vigentes | 2.331 | 0 | SQL PT-11 = 0 |
| Incremental | flag aspiracional | real (anti-join + parcial) | test PT-7 |
| Cobertura cartera vigente | 1,3% | tramos publicados con presupuesto | docs/eval/ESCALA |
| Tests | 72 | ≥ 76 (post PT-16) | `uv run pytest` |

---

# PLAN SOTA 2026-07 (PT-15…PT-22) — specs completas en `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`

#### [PT-15] Fuga `modelo` + caché prompt-aware — **✅ HECHO 2026-07-10 (`7f776b1`)**

`l3_model` resuelto dentro de `classify_cascade_dataframe`; `L3CacheEntry` gana
`prompt_version` (triple match); caché v1→v2; `grep "gemini-2.5-flash" src/` → 0
(queda solo `llm/provider.py:DEFAULT_L3_MODEL` como default explícito, no fallback ciego).

#### [PT-16] Saneo / simplificación — **✅ HECHO 2026-07-10 (`7f776b1`)**

Borrados `GeminiClient`/`OpenAIClient`/`enrich_taxonomy_legacy.py`/`requirements.txt`/
taxonomía csv-json duplicada/`docs/estructura_proyecto.md`; `_pick_column`
consolidado en `text_utils.pick_column`; `docs/eval/` commiteado (PT-17);
`test_classifier_l2.py` nuevo. pytest 105 (objetivo era ≥76).

#### [PT-17] Golden real (absorbe PT-10) — **M, insumo 👤 entregado**

Fuente: `informe_expost.duckdb` (n=2.357). Conversor + aliases + gate estrato `expost`.
Done: `eval_golden.py --ci` verde con golden completo.

#### [PT-18] Gate publicación + re-publish (absorbe PT-9/PT-11) — **✅ código HECHO 2026-07-09; 👤 re-publish GATED por PT-23**

Réplica `store_gate.py` OBSRATE; `--allow-rejected`; integrado en `publish_to_store` + CLI.
Tests: `tests/test_store_gate.py` (4); pytest total 83. Re-publish bloqueado hasta validar prompts (PT-23).

#### [PT-23] Holdout + eval L3 real — **✅ HECHO 2026-07-09**

Split dev/holdout 80/20 estratificado (`golden_split.py`); golden v2.1.0 con tags `dev`/`holdout`.
`eval_golden.py --estrato dev|holdout --real` reporta métricas cascada y L3; `--l3-limit` para piloto.
Gate CI sigue solo L1+L2 estrato `expost`. Publish al store **después** de holdout aceptable.

#### [PT-19] Backend HITL — **✅ HECHO 2026-07-15**

FastAPI read-only sobre el store (D-13 intacto: veredictos a JSONL aparte).
`src/projecttype/review/` (hitl_base `JsonlHitlStore[T]`, schemas `RevisionTipoRecord`
+ `Veredicto`, `TipoReviewStore` = snapshot memoria de enr_tipo_proyecto + contexto
CONSULTAS_EBI + CoT del caché L3 + veredictos) y `src/projecttype/api/` (create_app,
mount_spa, routers). Endpoints: `/api/health`, `/api/review/{summary,queue,item/{ebi},
item/{ebi}/verdict,reload}`, `/api/manual/{subsectores,pendientes,clasificar/{ebi}}`,
`/api/catalogo/arbol`, `/api/config/{files,file/{kind}}` (editor de prompts, base PT-22).
CLI `projecttype serve` puerto 8788. Deps: fastapi/uvicorn (+httpx dev). 9 tests
TestClient (test_api_hitl.py). Boot real de uvicorn verificado.

**Nota de alcance (D-19 revisado 2026-07-15):** el snapshot NO exige el re-publish
👤 de PT-18. La cola de revisión se llena con lo que haya en el store (hoy poco),
pero `/manual` (clasificar subsectores sin cobertura sobre CONSULTAS_EBI + taxonomía)
y `/config` (afinar prompts/casos borde) son **usables ya**, sin la tanda pagada.
El editor de la taxonomía queda de solo-lectura (cambia taxonomy_hash → PT-22).

#### [PT-20] SPA v1 — **L, pendiente (PRÓXIMO)**

React/Vite clon OBSRATE; `/revision` + `/manual` + `/config` (editor prompts) +
`/catalogo`. Consume la API de PT-19 (ya lista). CI job `web` bloqueante.
Vite dev 5176 (proxy `/api`→8788). `web/dist` → `mount_spa` ya lo sirve.

#### [PT-21] Loop salida HITL — **M, pendiente**

`hitl export-golden` + `hitl publish`; `--enable-publish` opt-in; guard anti-pisada.
Dep: SC-17 + PT-18 + PT-19.

#### [PT-22] v2 editor catálogo/prompts — **L, DIFERIDA**

Patrón config-router OBSRATE + eval obligatorio. Gated: PT-17 + PT-20.

#### [PT-25] Transporte LLM: paridad de robustez con OBSRATE — **✅ código HECHO 2026-07-10; falta smoke real 👤**

**Origen.** Diagnóstico 2026-07-10: los "problemas con Google Cloud" que OBSRATE no
tiene venían de tres brechas del transporte L3.

1. **✅ (SC-19, commons)** Los 429 con `retryDelay` del servidor ya se respetan:
   `RetryProvider` espera lo que pide Google (tope 90 s) en vez del backoff ciego
   0.5→4 s que agotaba los 4 retries en ~7 s dentro de la misma ventana de throttle
   y tiraba la fila a "Error LLM" residual. PT lo hereda sin tocar código.
   `vertex.py` de commons ahora también extrae el `retryDelay` (antes solo AI Studio).
2. **✅ L3 vía `structured_output`.** `SniCommonsLLMClient.complete_json` ya no usa
   `chat` + `_extract_json` (regex de fences + `json.loads`, eliminados junto con
   `JSONParseError`) — llama `provider.structured_output(messages, L3ResponseModel,
   ...)`. El backend (Vertex/Gemini `response_schema` nativo, Anthropic tool-use)
   fuerza el schema y valida con Pydantic; un mismatch ya no cae silencioso a
   confianza 0 — llega como `LLMResponseError` (`LLMError`), que
   `_classify_one_l3_row` en `pipeline_cascade.py` sigue capturando igual que
   antes (row a residual "Error LLM (lote protegido)", contado en `l3_failures` —
   **sin regresión**: `classify_row` deliberadamente NO atrapa `LLMError`, para
   que el conteo de fallos del lote siga funcionando en el nivel que corresponde).
3. **✅ `projecttype verify-llm [--provider --model]`.** Smoke de dos pasos (chat
   simple + `structured_output` con `L3ResponseModel`, el mismo camino exacto que
   usa L3 en producción) antes de correr `enrich --enable-l3`; falla temprano con
   mensaje accionable si faltan credenciales/ADC en vez de descubrirlo a mitad
   de una corrida pagada.

**Verificado:** 108 tests (3 nuevos: `test_verify_llm.py` + reescritura de
`test_sni_commons_client.py` sobre `structured_output`); ruff 0; mypy --strict 0;
`eval_golden --ci` gate aprobado, `prompt_version` sin cambios (no invalida caché).

**Pendiente (👤):** smoke real contra Vertex/AI Studio de verdad
(`projecttype verify-llm` con credenciales reales) — lo anterior solo verificó
con providers stub/echo, sin red.

#### [PT-24] Multi-tipo L3 (fallback extremo) — **✅ HECHO 2026-07-10**

**Objetivo.** Proyectos integrales (PMIB, saneamiento, educación compuesta) con ≥2 obras
evidenciadas: L3 devuelve tipo principal + hasta 2 secundarios; métrica multi-hit en eval.

**Implementado:**
- Schema L3: `tipos_secundarios[]`, `multi_tipo` (`l3_schema.py`, `l3.yaml`)
- Clasificador: validación contra lista cerrada, propagación a cascada/caché v3
- Métricas: `multi_hit_l3_puro`, `exactos_multi_hit_l3_puro` en `eval_golden.py`
- Auditoría manual 13 casos: `docs/eval/auditoria_l3pure13_2026-07-10.md`

**Done-cuando:** pytest verde; re-eval `--l3-pure 100` con Vertex (👤) reporta multi-hit;
holdout congelado hasta validar en dev. Store: principal en `tipo_proyecto`; secundarios
solo en metadatos L3 (columna store → SC-17 futuro).

---

#### [PT-14] Selección desde SNI — **✅ HECHO 2026-07-06 (`3200751`)**

**Objetivo.** Consumir `sel_tipo_proyecto_<id>` publicada por SNI Intelligence.

**Implementado:** `enrich --from-selection <id>` lee tabla de selección vía commons
(`SEL_PROYECTOS_CONTRACT` / SC-16). Tests en `tests/test_from_selection.py` (5).

**Done-cuando:** ✅ tests verdes; `--from-store` y `--from-selection` mutuamente excluyentes.

---
## Notas (NO regresar)
- **Regla taxonomía:** no editar `data/taxonomy/taxonomia_tipos_proyecto.yaml` fuera de
  PT-22 — altera `taxonomy_hash` e invalida incremental/caché/store.
- El código BIP en el store es canónico **SIN** dígito verificador (`store_publish`
  ya normaliza quitando `-N`; test `test_bip_code_normalized_for_join` lo protege).
- Añadir tipos a la taxonomía = editar `data/taxonomy/taxonomia_tipos_proyecto.yaml`,
  no el pipeline. (Corregido 2026-06-26: "ciclovía" SÍ es un tipo — `CICLOVIAS URBANAS`
  y `SENDAS MULTIPROPOSITO (CICLOVIAS)` ya están en la taxonomía.)
- SNI ya **consume** `enr_tipo_proyecto` (SNI-12, `--filter tipo_proyecto=<id|nombre>`):
  el atributo que publicas aquí ya es filtrable aguas abajo.

## Hecho (log)
PT-1/2 (Fase 0: git + N+1 eliminado en la cascada), PT-4 (cliente LLM → sni-commons),
**PT-5** (escribe `enr_tipo_proyecto` al store; JOIN con EBI 14.806 matches; bug del
dígito verificador atrapado con datos reales, commit f941fb5), **PT-6** (2026-06-09:
ciclo store→store — `store_input.py` lee CONSULTAS_EBI y mapea SEC/SBS_CLAVE→nombres
vía `sni_commons.reference`, dedupe por proyecto a la solicitud más reciente; CLI
`projecttype enrich --from-store` con guard de publish parcial; smoke real:
5 proyectos del store clasificados y dry-run del diff), **PT-8** (pytest sin
`sys.path` hacks + **mypy --strict 0 errores** + ruff limpio en src/scripts/tests;
de paso se rompió un import circular l2↔cascada que dependía del orden de import,
y se pasa `writer=` al ledger del store v1.1), **PT-9** (2026-07-02: metadatos SC-13
en publish — `inference_metadata.py`, contrato validado, 4 tests), **PT-10** (2026-07-02:
golden fixture + `eval_golden.py --ci` + gate CI; golden real → **PT-17**, 3 tests),
**PT-7** (2026-07-06: incremental `242af99`, 4 tests), **PT-14** (2026-07-06:
`--from-selection` `3200751`, 5 tests).
