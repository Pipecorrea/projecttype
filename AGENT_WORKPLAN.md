# AGENT_WORKPLAN — ProyectType

> **Contexto obligatorio:** lee primero **`ECOSISTEMA.md`** (mapa del ecosistema +
> tu rol) y `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md` (estado vivo). Rumbo:
> `/Users/felipecorrea/Vs/PROPUESTA_SOTA_2026-06.md` (los próximos pasos de este
> repo salen de ahí). Visión y alcance del repo: `VISION.md`.
>
> **Estado:** **enriquecedor** funcionando, ciclo **store→store completo** (PT-6):
> `proyecttype enrich --from-store` lee CONSULTAS_EBI, clasifica y publica
> `enr_tipo_proyecto`. Cliente LLM unificado en sni-commons (PT-4). py3.12.
> 56 tests (**pytest**, PT-8), mypy **--strict**, ruff limpio — CI bloqueante.
> Cascada L1 (keywords) → L2 (embeddings) → L3 (LLM).

## Verde antes de commitear
`uv run pytest` (56) · `uv run ruff check src scripts tests` · `uv run mypy src`
(--strict) — **lo mismo que corre CI (bloqueante)**.

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

## [PT-7] Re-clasificación incremental — **pendiente principal** (PROPUESTA R2 §13)
`upsert_dataframe` ya es no destructivo. Clasificar solo los BIP nuevos/sin tipo
(no los 9k cada vez), usando el `l3_cache` + `read_pandas("enr_tipo_proyecto")` para
saber qué ya está clasificado con la versión actual del enricher. Pensado para
integrarse al futuro comando `eco refresh` del ecosistema.
⚠️ Relacionado: hoy un publish PARCIAL marca el resto como ausente
(`_present_in_latest=false`) — el CLI lo advierte y pide confirmación con
`--limit`; PT-7 debería resolverlo bien (publish incremental que no resetee
el flag, coordinado con sni-commons).
- **Done-cuando:** `enrich --incremental` salta BIP ya clasificados.

## [PROPUESTA §4.1] Versionar la inferencia en el dato — al tocar el clasificador
`enr_tipo_proyecto` ya registra `enricher_version` y writer/schema_version en el
ledger; falta añadir **taxonomía, modelo y versión de prompt** como metadato al
escribir, para que filas viejas y nuevas sean distinguibles cuando cambie el
clasificador (o el proveedor LLM — §4.0).

## [PROPUESTA §4.1/R3 §19] Golden-set bajo formato común
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
y se pasa `writer=` al ledger del store v1.1).
