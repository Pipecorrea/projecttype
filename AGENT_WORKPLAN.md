# AGENT_WORKPLAN — ProyectType

> **Contexto obligatorio:** lee primero **`ECOSISTEMA.md`** (mapa del ecosistema +
> tu rol) y `/Users/felipecorrea/Vs/ESTADO_ECOSISTEMA.md` (estado vivo).
>
> **Estado:** **enriquecedor** funcionando, ciclo **store→store completo** (PT-6):
> `proyecttype enrich --from-store` lee CONSULTAS_EBI, clasifica y publica
> `enr_tipo_proyecto`. Cliente LLM unificado en sni-commons (PT-4). py3.12.
> 55 tests (**pytest**, PT-8), mypy **--strict**, ruff limpio — CI bloqueante.
> Cascada L1 (keywords) → L2 (embeddings) → L3 (LLM).

## Verde antes de commitear
`uv run pytest` (55) · `uv run ruff check src scripts tests` · `uv run mypy src`
(--strict) — **lo mismo que corre CI (bloqueante)**.

---

# PENDIENTES (orden sugerido)

## [PT-7] Re-clasificación incremental — bajo
`upsert_dataframe` ya es no destructivo. Clasificar solo los BIP nuevos/sin tipo
(no los 9k cada vez), usando el `l3_cache` + `read_pandas("enr_tipo_proyecto")` para
saber qué ya está clasificado con la versión actual del enricher.
⚠️ Relacionado: hoy un publish PARCIAL marca el resto como ausente
(`_present_in_latest=false`) — el CLI lo advierte y pide confirmación con
`--limit`; PT-7 debería resolverlo bien (publish incremental que no resetee
el flag, coordinado con sni-commons).
- **Done-cuando:** `enrich --incremental` salta BIP ya clasificados.

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
dígito verificador atrapado con datos reales, commit f941fb5), **PT-6** (2026-06-09:
ciclo store→store — `store_input.py` lee CONSULTAS_EBI y mapea SEC/SBS_CLAVE→nombres
vía `sni_commons.reference`, dedupe por proyecto a la solicitud más reciente; CLI
`proyecttype enrich --from-store` con guard de publish parcial; smoke real:
5 proyectos del store clasificados y dry-run del diff), **PT-8** (pytest sin
`sys.path` hacks + **mypy --strict 0 errores** + ruff limpio en src/scripts/tests;
de paso se rompió un import circular l2↔cascada que dependía del orden de import,
y se pasa `writer=` al ledger del store v1.1).
