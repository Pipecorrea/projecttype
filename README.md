# ProjectType

**Enriquecedor de tipo de proyecto del ecosistema SNI/BIP.** Clasifica cada
proyecto de inversión pública (BIP) en un **tipo** de una taxonomía cerrada
(jardín infantil, ruta, puente urbano, alumbrado público…) mediante una cascada
costo-consciente de tres niveles — L1 reglas → L2 embeddings → L3 LLM — y
publica el resultado a la tabla `enr_tipo_proyecto` del store canónico DuckDB.

> El **tipo de proyecto NO existe en los datos oficiales del BIP** (EBI/RATE).
> Este repo lo crea. Eso resuelve el caso de uso del dueño ("quiero todos los
> proyectos de jardín infantil de la región X"): SNI Intelligence filtra por
> tipo (`--filter tipo_proyecto=…`) gracias a lo que se publica aquí.

Contexto del ecosistema: [`ECOSISTEMA.md`](ECOSISTEMA.md) (rol y reglas) ·
`/Vs/ESTADO_ECOSISTEMA.md` (estado vivo) · `/Vs/PROPUESTA_SOTA_2026-06.md`
(rumbo). Tareas de este repo: [`AGENT_WORKPLAN.md`](AGENT_WORKPLAN.md). Visión:
[`VISION.md`](VISION.md).

---

## Instalación

Requiere Python ≥ 3.12, [uv](https://docs.astral.sh/uv/) y el repo hermano
`../sni-commons` (se consume por path editable mientras no haya índice privado):

```bash
git clone <este-repo> ProjectType        # junto a sni-commons
cd ProjectType
uv sync --extra dev
```

Variables de entorno (ver `.env.example`):

- `BIP_DATA_DIR` — directorio del store canónico (`~/bip_data`). Obligatoria
  para el ciclo store→store.
- Para L3 (LLM): `GEMINI_API_KEY`/`GEMINI_MODEL`, `OPENAI_API_KEY`, u
  `OLLAMA_BASE_URL`/`OLLAMA_MODEL` según proveedor. El cliente por defecto es
  el unificado de `sni_commons.llm` (neutralidad de proveedor — el proveedor
  ministerial sigue indefinido).

## Verde antes de commitear (lo mismo que corre CI, bloqueante)

```bash
uv run pytest                          # 72 tests
uv run ruff check src scripts tests
uv run mypy src                        # --strict (configurado en pyproject)
```

Tests sueltos: `uv run pytest tests/test_classifier_l1.py` o
`uv run pytest tests/test_classifier_l1.py::TestClassifierL1::test_biblioteca_asignada -q`.

---

## Cómo se clasifica: la cascada L1 → L2 → L3

Cada nivel corre **solo sobre el residual** del anterior (estados `ambiguo` o
`sin_match`). La idea es costo-consciente: lo barato y determinista primero,
el LLM al final y solo para lo que de verdad lo necesita.

| Nivel | Módulo | Método | Cuándo decide |
|---|---|---|---|
| **L1** | `classifier_l1` + `scorer` | Scoring determinista por keywords de la taxonomía: fuertes (nombre ×3, descripción ×2), débiles (×1), exclusiones (−5), bonus por nombre de tipo (+4) y por tipos compuestos (`composite.py`). | `asignado` si score ≥ 1.0 y margen sobre el segundo ≥ 2.0; si no, `ambiguo`/`sin_match` → pasa a L2. |
| **L2** | `classifier_l2` + `embeddings` + `tipo_embedder` | Similitud coseno con sentence-transformers (`paraphrase-multilingual-MiniLM-L12-v2`), embeddings de tipos cacheados por subsector en `data/taxonomy/embeddings_cache/`. | `asignado` si similitud ≥ 0.48 y margen ≥ 0.12; si no → pasa a L3 (si está habilitado). |
| **L3** | `classifier_l3` + `prompts` | LLM con lista **cerrada** de tipos del subsector, salida JSON estructurada (pydantic), few-shot curado + minado de etiquetas manuales, y **caché JSONL por código BIP** (`l3_cache.py`) — un BIP ya clasificado no vuelve a pagar una llamada. | `asignado` si confianza ≥ 0.75 y el `tipo_id` valida contra la taxonomía. |

Estados posibles (`EstadoClasificacion`): `asignado` · `ambiguo` · `sin_match`
· `sin_taxonomia` (no hay tipos para ese (sector, subsector) en la taxonomía).

Orquestación: `ClassifierCascade` (fila a fila) y
`pipeline_cascade.classify_cascade_dataframe` (lote completo con Polars).

### La taxonomía

`data/taxonomy/taxonomia_tipos_proyecto.yaml` — **326 tipos** organizados en
16 sectores y 84 subsectores, con definición, magnitudes y keywords por tipo.
Añadir un tipo nuevo = editar el YAML, **no** el pipeline. `aliases.py` mapea
nombres de sector/subsector del BIP con tipos o grafías alternativas a las
claves canónicas de la taxonomía.

---

## Uso

### Camino de producción: ciclo store→store (PT-6)

```bash
# Clasificar TODO lo que hay en CONSULTAS_EBI y publicar enr_tipo_proyecto
uv run projecttype enrich --from-store

# Con nivel LLM para el residual de L1/L2
uv run projecttype enrich --from-store --enable-l3

# Piloto: clasificar 100 y ver el diff del store SIN escribir
uv run projecttype enrich --from-store --limit 100 --dry-run

# Además guardar los resultados crudos a CSV
uv run projecttype enrich --from-store --out data/output/resultados.csv
```

Qué hace `enrich --from-store`:

1. **Lee** `CONSULTAS_EBI` del store (`store_input.py`), deduplica a una fila
   por proyecto (gana la solicitud más reciente) y mapea
   `SEC_CLAVE`/`SBS_CLAVE` → nombres vía `sni_commons.reference`.
2. **Clasifica** con la cascada (L3 opcional, con caché).
3. **Publica** `enr_tipo_proyecto` (`store_publish.py`) vía
   `BipDataStore.upsert_dataframe` — incremental y no destructivo, validado con
   `ENR_TIPO_PROYECTO_CONTRACT` y firmado en el ledger `_loads`
   (`writer=projecttype@<versión>`).

⚠️ **Guard de publish parcial:** un publish con `--limit` marca el resto de la
tabla como ausente del último snapshot (`_present_in_latest=false`) y los
consumidores dejarían de verlo. El CLI lo advierte y pide confirmación; los
pilotos van con `--dry-run`. (PT-7 lo resolverá bien con publish incremental.)

### Reglas del store (no negociables)

- **EBI_CODIGO canónico = SIN dígito verificador** (`30069417`, no
  `30069417-0`). `store_publish` normaliza quitando el `-N`; sin esto el JOIN
  con EBI da 0 filas (bug real atrapado en PT-5; lo protege
  `test_bip_code_normalized_for_join`).
- El store vive en `~/bip_data/` (datos, no código). **Nunca** versionar
  `.duckdb`/CSV. Un solo escritor a la vez.
- Validar columnas con contrato: un rename falla claro
  (`MissingColumnsError`), no se propaga como `None`.

### Camino CSV (calibración / evaluación)

Sigue vivo para trabajar contra la submuestra manual y calibrar umbrales:

```bash
uv run python scripts/classify_l1.py                       # solo L1
uv run python scripts/classify_cascade.py                  # L1+L2 → CSV
uv run python scripts/classify_cascade.py --enable-l3 --l3-provider google
uv run python scripts/classify_cascade.py --enable-l3 --l3-limit 100   # piloto L3
uv run python scripts/enrich_to_store.py data/output/resultados_l1_l2_l3.csv  # CSV → store (PT-5)

uv run python scripts/build_revision_manual.py     # Excel de revisión L1 vs etiquetas manuales
uv run python scripts/build_few_shot_examples.py   # minar few-shot de etiquetas manuales
uv run python scripts/calibrate_l2.py              # calibrar umbrales L2
uv run python scripts/l3_status.py                 # estado del caché/progreso L3
```

---

## Qué hace HOY y qué no

**Hoy:** ciclo store→store completo. En el store hay **2.331 proyectos
clasificados** publicados en `enr_tipo_proyecto` (14.806 matches con las filas
de `CONSULTAS_EBI`), ya consumidos por SNI Intelligence (`--filter
tipo_proyecto=`).

**Todavía NO (plan SOTA 2026-07):** golden real (PT-17), gate publish (PT-18),
UI HITL (PT-19…21). Ver `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md` y `AGENT_WORKPLAN.md`.

**Incremental (PT-7 ✅) y selección SNI (PT-14 ✅)** ya funcionan en código.

**Fuera de alcance:** análisis/reportes (SNI Intelligence). **Dentro (D-19):** UI
de validación/clasificación del atributo — tooling interno, no reportería.

## Estructura del repo

```
src/projecttype/
  cli.py                 # CLI `projecttype enrich --from-store` (typer)
  classifier_cascade.py  # orquestador L1→L2→L3 (fila a fila)
  pipeline_cascade.py    # lote completo (Polars) + integración caché L3
  classifier_l1.py / scorer.py / composite.py / aliases.py   # nivel reglas
  classifier_l2.py / embeddings.py / tipo_embedder.py        # nivel embeddings
  classifier_l3.py / prompts.py / l3_schema.py / l3_cache.py # nivel LLM
  prompt_context.py / few_shot_mining.py                     # contexto y few-shot L3
  llm_client.py          # adaptador SniCommonsLLMClient (default) + clientes legacy
  store_input.py         # PT-6: CONSULTAS_EBI → input de la cascada
  store_publish.py       # PT-5: resultados → enr_tipo_proyecto (normaliza EBI_CODIGO)
  taxonomy.py            # carga del YAML de taxonomía
  evaluation.py          # comparación vs submuestra manual (Submuestra_tp.xlsx)
data/taxonomy/           # taxonomía YAML + caché de embeddings
data/prompts/            # prompt L3 + few-shot (curado y minado)
scripts/                 # camino CSV, calibración y evaluación
tests/                   # 72 tests (pytest)
```
