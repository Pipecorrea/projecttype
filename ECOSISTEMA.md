# Ecosistema SNI/BIP — contexto para `ProyectType`

> **Por qué existe este archivo:** este repo es **parte de un ecosistema** (6 proyectos
> + 1 librería compartida), no una app aislada. Si trabajas solo aquí (tú o un agente
> de Cursor), lee esto primero para no perder el contexto del conjunto.

## Tú en el ecosistema

**Eres `ProyectType`** — un **enriquecedor**: clasificas el **tipo de proyecto** (cascada
L1 keywords → L2 embeddings → L3 LLM), un atributo que NO existe en los datos del BIP.

- **Tu conexión:** ciclo **store→store completo** (PT-6): `proyecttype enrich
  --from-store` lee `CONSULTAS_EBI`, clasifica y **escribe `enr_tipo_proyecto` al
  store** (`store_input.py` + `store_publish.py`); **SNI Intelligence lo consume**
  para filtrar por tipo. (El camino CSV `scripts/enrich_to_store.py` queda para
  calibración/eval.)
- **Regla #1 tuya:** al escribir, normaliza **EBI_CODIGO sin dígito verificador** (quita
  el `-N`), o el JOIN con `CONSULTAS_EBI` da 0 filas (bug real ya atrapado en PT-5; lo
  protege `test_bip_code_normalized_for_join`). Tu cliente LLM ya usa `sni_commons.llm`.

## El ecosistema en 30 segundos

Dominio: **Banco Integrado de Proyectos (BIP) / Sistema Nacional de Inversiones (SNI)**
de Chile. Modelo **hub-and-spoke** alrededor de un **store de datos canónico** (DuckDB
en `~/bip_data/`, fuera de los repos — datos, no código).

```
                  ┌─────────────────────────────┐
   Planillas      │   STORE CANÓNICO (DuckDB)    │
   EBI/RATE  ───► │   ~/bip_data/bip_data.duckdb │ ◄── enriquecedores escriben
   (por correo,   │   CONSULTAS_EBI · HISTORIAL_ │     (enr_tipo_proyecto,
   vía bip-data)  │   RATE · enr_*               │      enr_observaciones)
                  └──────────────┬──────────────┘
                          leen   │
              ┌──────────────────┼──────────────────┐
        SNI Intelligence     OBSRATE            ProyectType
        (cerebro/reportes)   (observaciones)    (clasifica tipo)

   Aparte del store: BIP CD baja la carpeta digital (documentos) y RAG
   verifica cumplimiento normativo sobre esos documentos.
```

## Quién es quién

| Proyecto | Rol | Conexión |
|---|---|---|
| **sni-commons** | Librería compartida: `llm` · `contracts` · `io` · `store`. | La consumen todos por path editable. |
| **SNI Intelligence** | El "cerebro": reportes (REGI, Historial RATE) + selección de proyectos aguas abajo. | Lee EBI/RATE + `enr_*` del store. |
| **ProyectType** | Enriquecedor: clasifica el tipo de proyecto. | Escribe `enr_tipo_proyecto` al store. |
| **OBSRATE** | Enriquecedor: ordena/deduplica observaciones RATE. | Escribe `enr_observaciones` al store. |
| **BIP CD** | Extracción: scraper de la Carpeta Digital + parser. Baja los documentos de cada proyecto. | Planillas → store (por correo); baja carpetas para RAG. |
| **RAG** | Silo normativo (RIS/Metodologías/NIP → Neo4j). Verifica cumplimiento normativo. | No usa el store; se conecta vía los documentos que baja BIP CD. |
| **Parser** | 🗄️ Retirado — absorbido por BIP CD. No usar. | — |

## Reglas que NO se rompen

1. **Se comunican vía el STORE, no importándose entre sí.** El único código compartido es `sni-commons`.
2. **`sni-commons` no importa a sus consumidores**; su núcleo (llm/contracts/io) no depende de DuckDB ni SDKs cloud (extras + import perezoso).
3. **El store es canónico**, vive en `~/bip_data/` (datos, no código — **nunca** versionar `.duckdb`/CSV). Entrada humano-en-el-loop: planillas EBI/RATE por **correo** → `bip-data load` (incremental, no destructivo).
4. **EBI_CODIGO canónico = SIN dígito verificador** (`30069417`, no `30069417-0`). Normaliza quitando el `-N` antes de joinear.
5. **Valida columnas con contrato**: un rename debe fallar claro (`MissingColumnsError`), no propagarse como `None`.
6. **Verde antes de commitear** + **nunca commitear datos** (`data/`, `*.csv`, `*.duckdb`, `*.parquet`, `*.rar`).

## El flujo, de punta a punta

1. Planillas **EBI/RATE** por correo → `bip-data load` → **store**.
2. **ProyectType** y **OBSRATE** leen del store, enriquecen y **escriben `enr_*`** de vuelta.
3. **SNI Intelligence** lee EBI/RATE + `enr_*`, genera **reportes** y **selecciona** los BIP relevantes.
4. **BIP CD** baja la **carpeta digital** (documentos) de esos proyectos.
5. **RAG** cruza esos documentos contra la **normativa** y verifica cumplimiento.

## La verdad viva (no la dupliques aquí)

- **`/Vs/ESTADO_ECOSISTEMA.md`** — foto actual real (estado por proyecto, datos cargados, reglas). **Manda sobre cualquier otro `.md`.**
- **`/Vs/PROPUESTA_SOTA_2026-06.md`** — el rumbo vigente (R0–R4); para este repo:
  PT-7 incremental, golden-set bajo formato común y versionar modelo/prompt (§4.1).
- **`/Vs/FLUJO_ECOSISTEMA.md`** — el flujo en lenguaje no-técnico.
- **`AGENT_WORKPLAN.md`** (este repo) — las tareas concretas pendientes aquí.

> Este archivo es el **mapa durable** (roles, store, reglas). Para el **estado cambiante**
> (qué está hecho/falta), ve siempre a los documentos de arriba.
