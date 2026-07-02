# AGENT_WORKPLAN — ProyectType

> **Contexto obligatorio:** lee primero **`ECOSISTEMA.md`** (mapa del ecosistema +
> tu rol) y `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md` (estado vivo). Rumbo:
> `/Users/felipecorrea/Vs/PROPUESTA_SOTA_2026-06.md` (los próximos pasos de este
> repo salen de ahí). Visión y alcance del repo: `VISION.md`.
>
> **Estado:** **enriquecedor** funcionando, ciclo **store→store completo** (PT-6):
> `proyecttype enrich --from-store` lee CONSULTAS_EBI, clasifica y publica
> `enr_tipo_proyecto`. Cliente LLM unificado en sni-commons (PT-4). py3.12.
> 63 tests (**pytest**, PT-8/9/10), mypy **--strict**, ruff limpio — CI bloqueante.
> Cascada L1 (keywords) → L2 (embeddings) → L3 (LLM).

## Verde antes de commitear
`uv run pytest` (63) · `uv run ruff check src scripts tests` · `uv run mypy src`
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

# ⭐ PLAN 2026-07 — lo que ordena la evaluación estratégica (creado 2026-07-02)

> Master de referencia: `/Vs/EVALUACION_ESTRATEGICA_2026-07.md` §8.4.
> Absorbe los pendientes previos: [PROPUESTA §4.1] versionar inferencia → **PT-9**;
> [PROPUESTA §4.1/R3 §19] golden-set → **PT-10**; PT-7 conserva su ID y se precisa abajo.

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

#### Secuencia

```
PT-9 (metadatos de inferencia)  ← espera SC-13 de sni-commons (shim local si no está)
  └→ PT-10 (golden en el repo + gate CI)  ← espera SC-14 (formato común)
       └→ PT-7 (incremental real)  ← espera SC-13 (mark_missing=False)
            └→ PT-11 (saneo del fósil PT-5)
PT-12 (rutas/entrada única) — en cualquier momento, no bloquea
PT-13 (escala a cartera vigente 👤) — SOLO con PT-9+PT-10+PT-7 cerrados
```

#### [PT-9] Metadatos de inferencia en `enr_tipo_proyecto` — **HECHO 2026-07-02**

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

#### [PT-10] Golden-set EN el repo + gate en CI — **HECHO 2026-07-02 (fixture; Submuestra pendiente 👤)**

**Objetivo.** La vara fija. Hoy la submuestra de calibración no está en el repo y el
baseline (prec 79,8% / cob 65,6% / e2e 52,3%, 2026-06-19) vive en la memoria.

**Cambios:**
- Convertir `data/raw/Submuestra_tp.xlsx` (col `tipo_proyecto`, header fila 0;
  descriptores = input) al formato `sni_commons.eval` (SC-14) →
  `data/golden/golden_tipo_proyecto.yaml` **commiteado** (es etiqueta humana, chica,
  cara de regenerar — política de datos derivados, misma que RAG).
- Script `scripts/eval_golden.py`: corre L1+L2 REALES (deterministas, sin red) +
  L3 con `MockLLMClient` en modo CI; con `--real` usa el proveedor configurado (👤).
  Emite `ResultadoEval` (JSON versionado en `docs/eval/`) + matriz de confusión
  (CSV en `docs/eval/`).
- Gate: `scripts/eval_golden.py --ci` → exit 1 si precisión L1+L2 < baseline
  registrado (79,8%) o cobertura < 65,6% (umbrales en `data/golden/umbrales.yaml`,
  versionados — se suben cuando mejore, NUNCA se bajan sin decisión del dueño
  anotada en DECISIONES.md). Job nuevo en `.github/workflows/ci.yml`.
- **Regla de cambio (va al workplan y a CLAUDE.md):** ningún cambio de modelo /
  prompt / umbral / taxonomía sin corrida antes/después registrada en `docs/eval/`.

**Done-cuando:**
- `uv run python scripts/eval_golden.py --ci` verde en local y en CI; un cambio
  deliberado que degrade L1 (test que muta un umbral del scorer) lo pone rojo.
- El baseline queda REPRODUCIDO desde el repo limpio (clonar → sync → eval) y
  anotado con fecha en `docs/eval/`. La mejora de TRANSPORTE URBANO (reglas
  discriminantes, hoy "no reproducible en CI") queda medida aquí o se declara
  no confirmada.

**Implementado:** `data/golden/golden_tipo_proyecto.yaml` (fixture 12 casos —
⚠️ **bloqueador:** `Submuestra_tp.xlsx` ausente; regenerar con
`scripts/convert_submuestra_to_golden.py`), `umbrales.yaml`, `scripts/eval_golden.py`,
`golden_eval.py`, job CI, tests `tests/test_eval_golden.py` (3). Gate verde en fixture.

#### [PT-7] Re-clasificación incremental REAL (spec previa, ahora desbloqueada)

**Objetivo.** Clasificar solo BIP nuevos/cambiados; publish parcial que NO marca el
resto como ausente. (La spec original de PT-7 sigue válida; esto la precisa.)

**Cambios:**
- `enrich --incremental`: anti-join contra
  `read_pandas("enr_tipo_proyecto", where=…)` por (`EBI_CODIGO`,
  `taxonomy_hash`, `enricher_version`, `prompt_version`): si los 4 coinciden, la
  fila se salta; si cambió taxonomía/prompt/versión, se re-clasifica.
- Publicar con `upsert_dataframe(..., mark_missing=False)` (SC-13). El guard actual
  de publish parcial (`--limit` + confirmación) se conserva para el modo NO incremental.

**Done-cuando:**
- Tests: corrida incremental sobre store fixture con 3 clasificados vigentes + 2
  nuevos → clasifica SOLO 2; ninguno de los 3 pierde `_present_in_latest`; cambiar
  `taxonomy_hash` fuerza re-clasificación de los 3.
- `uv run proyecttype enrich --from-store --incremental --dry-run` imprime el conteo
  a clasificar vs saltados (pegar salida real en el log).

#### [PT-11] Saneo del fósil PT-5 en el store

**Objetivo.** Eliminar del dato vigente las 2.331 claves huérfanas con formato viejo
(con dígito verificador) que conviven con las 2.331 canónicas.

**Pasos:**
1. Diagnóstico reproducible: `scripts/diagnosticar_fosil.py` — cuenta filas vigentes
   cuya clave NO es `to_store_key(clave)` (SC-12) y las lista a CSV local.
2. El próximo publish completo (o el primer incremental PT-7) escribe SOLO claves
   canónicas; las huérfanas deben quedar `_present_in_latest=false` (el upsert
   completo con `mark_missing=True` lo hace solo — verificar, no borrar filas:
   el store es no destructivo, el fósil queda como historia).
3. Guard permanente en `store_publish.py`: si alguna clave saliente difiere de su
   `to_store_key`, ABORTA (test).

**Done-cuando (pegar salida en el log):**
```sql
SELECT count(*) FROM enr_tipo_proyecto
WHERE _present_in_latest AND EBI_CODIGO LIKE '%-%';   -- = 0
```
y el JOIN de control con EBI vuelve a 100%:
`SELECT count(*) FROM enr_tipo_proyecto e LEFT JOIN CONSULTAS_EBI c USING (EBI_CODIGO)
WHERE e._present_in_latest AND c.EBI_CODIGO IS NULL;` → = 0.

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
`uv run proyecttype enrich --from-store --dry-run --limit 5` funciona sin editar
nada; test de config para el error claro; `grep` de rutas hardcodeadas a
`data/output/...` en `src/` → 0 (quedan solo en `scripts/` de eval).

#### [PT-13] Escala a cartera vigente — por tramos, con presupuesto (👤 GATED)

**Objetivo.** Cobertura 1,3% → cartera vigente completa, SIN deuda inauditable.
**Bloqueada hasta cerrar PT-9 + PT-10 + PT-7.**

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
| Tests | 63 | ≥ 75 | `uv run pytest` |

---


## [PT-7] Re-clasificación incremental — **pendiente principal** (PROPUESTA R2 §13; PRECISADO en el plan 2026-07 arriba — implementar esa versión)
`upsert_dataframe` ya es no destructivo. Clasificar solo los BIP nuevos/sin tipo
(no los 9k cada vez), usando el `l3_cache` + `read_pandas("enr_tipo_proyecto")` para
saber qué ya está clasificado con la versión actual del enricher. Pensado para
integrarse al futuro comando `eco refresh` del ecosistema.
⚠️ Relacionado: hoy un publish PARCIAL marca el resto como ausente
(`_present_in_latest=false`) — el CLI lo advierte y pide confirmación con
`--limit`; PT-7 debería resolverlo bien (publish incremental que no resetee
el flag, coordinado con sni-commons).
- **Done-cuando:** `enrich --incremental` salta BIP ya clasificados.

## ~~[PROPUESTA §4.1] Versionar la inferencia en el dato~~ — **ABSORBIDO por PT-9 (plan 2026-07, arriba)**
`enr_tipo_proyecto` ya registra `enricher_version` y writer/schema_version en el
ledger; falta añadir **taxonomía, modelo y versión de prompt** como metadato al
escribir, para que filas viejas y nuevas sean distinguibles cuando cambie el
clasificador (o el proveedor LLM — §4.0).

## ~~[PROPUESTA §4.1/R3 §19] Golden-set bajo formato común~~ — **ABSORBIDO por PT-10 (plan 2026-07, arriba)**
Formalizar la submuestra manual (`data/raw/Submuestra_tp.xlsx` + `evaluation.py`)
como golden-set del ecosistema (formato común casos + esperado + métrica; corre
en CI con stub, real programado). Regla de cambio: ningún cambio de modelo/prompt
/umbral sin corrida antes/después registrada.

---
## Notas (NO regresar)
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
`proyecttype enrich --from-store` con guard de publish parcial; smoke real:
5 proyectos del store clasificados y dry-run del diff), **PT-8** (pytest sin
`sys.path` hacks + **mypy --strict 0 errores** + ruff limpio en src/scripts/tests;
de paso se rompió un import circular l2↔cascada que dependía del orden de import,
y se pasa `writer=` al ledger del store v1.1), **PT-9** (2026-07-02: metadatos SC-13
en publish — `inference_metadata.py`, contrato validado, 4 tests), **PT-10** (2026-07-02:
golden fixture + `eval_golden.py --ci` + gate CI; Submuestra_tp.xlsx pendiente 👤, 3 tests).
