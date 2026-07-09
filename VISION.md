---
tipo: vision
ambito: ProjectType
actualizado: 2026-07-09
---

# ProjectType — Visión y alcance

*Documento para el equipo: qué es, qué hace hoy, hacia dónde va y qué queda fuera.*

## El espíritu (qué problema resuelve y por qué existe)

Los datos oficiales del BIP dicen mucho de cada proyecto — sector, subsector,
montos, RATE — pero **no dicen QUÉ es el proyecto**: no existe un campo que
diga "esto es una ciclovía", "esto es un jardín infantil", "esto es un puente
urbano". La pregunta más natural del dueño del negocio — *"muéstrame todos los
proyectos de jardín infantil"* — no se puede responder con los datos crudos.

ProjectType existe para **crear ese atributo**: clasifica cada BIP contra una
taxonomía cerrada de 326 tipos (16 sectores, 84 subsectores) y publica el
resultado al store canónico, donde el resto del ecosistema lo consume como si
siempre hubiera existido. Y lo hace de forma **costo-consciente**: una cascada
donde lo barato y determinista (reglas por keywords) resuelve la mayoría, los
embeddings resuelven parte del resto, y el LLM — lo caro — solo ve el residual
que de verdad lo necesita, con caché por BIP para no pagar dos veces.

## Lo que hace hoy (alcance actual)

- ✅ **Cascada L1→L2→L3 completa.** L1 keywords deterministas (con tipos
  compuestos y exclusiones), L2 similitud por sentence-transformers, L3 LLM con
  lista cerrada de tipos del subsector, salida JSON validada, few-shot curado +
  minado de etiquetas manuales, y caché JSONL por código BIP. Cada nivel corre
  solo sobre el residual del anterior.
- ✅ **Ciclo store→store (PT-6).** `projecttype enrich --from-store` lee
  `CONSULTAS_EBI`, clasifica y publica `enr_tipo_proyecto` — sin CSV
  intermedios. En el store hay **2.331 proyectos clasificados** (14.806 matches
  con las filas de EBI) y **SNI Intelligence ya filtra por tipo** con ellos.
- ✅ **Publicación segura.** EBI_CODIGO normalizado sin dígito verificador
  (regla D-6; bug real atrapado en PT-5 y protegido por test), contrato de
  columnas, upsert no destructivo, firma en el ledger del store, y guard que
  exige confirmación (o `--dry-run`) ante un publish parcial.
- ✅ **Neutralidad de proveedor LLM.** L3 va por `sni_commons.llm` (PT-4):
  Gemini, OpenAI u Ollama local intercambiables — clave mientras el proveedor
  ministerial siga indefinido.
- ✅ **Calidad de ingeniería.** 72 tests pytest (PT-8/14), mypy `--strict`, ruff —
  los tres bloqueantes en CI.
- ✅ **Incremental y selección (PT-7/PT-14).** `enrich --incremental` salta BIP ya
  clasificados con la misma era; `enrich --from-selection` consume selecciones de SNI.
- 🧪 **Evaluación contra golden.** Andamiaje CI existe (fixture n=12); golden real
  (n≈2.357 desde `informe_expost.duckdb`) pendiente en PT-17 — ver
  `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`.
- 🔜 **UI HITL de validación/clasificación (D-19).** Cola de revisión de propuestas
  L1/L2/L3 + clasificación manual de subsectores sin cobertura — herramienta interna
  del enriquecedor (patrón OBSRATE), no reportería. Spec: PT-19…PT-21.

## Lo que debería llegar a hacer (visión)

Un enriquecedor que **se mantiene solo al ritmo de los datos**: cada carga
nueva de planillas EBI dispara (vía el futuro `eco refresh`) una clasificación
**solo de los proyectos nuevos o sin tipo**, en minutos y con costo LLM
marginal. Cada fila publicada lleva la **versión de taxonomía, modelo y prompt**
con que se clasificó, de modo que cuando cambie el clasificador — o llegue el
proveedor LLM institucional — las filas viejas y nuevas sean distinguibles y
re-clasificables selectivamente. Y la calidad deja de ser una opinión: la
submuestra manual formalizada como **golden-set** bajo el formato común del
ecosistema, con regla dura de "ningún cambio de modelo/prompt/umbral sin
corrida antes/después registrada" (PROPUESTA §4.1).

## Lo que falta para llegar (brechas, en orden)

Ver plan completo en `DIAGNOSTICO_Y_PLAN_SOTA_2026-07.md`. Resumen:

1. **PT-15 (P0)** — fuga de `modelo` y caché L3 ciego a `prompt_version`.
2. **PT-17** — golden real n≈2.357 + gate CI recalibrado (absorbe PT-10).
3. **PT-18** — gate de publicación + re-publish con metadatos (absorbe PT-9/PT-11).
4. **PT-19…PT-21** — UI HITL (validar, clasificar manual, exportar/publish) — [[DECISIONES#D-19 · ProjectType gana loop humano propio (UI de validación/clasificación manual)|D-19]].
5. **PT-13** — escala a cartera vigente por tramos (gated; recomendado tras UI).
6. **PT-16** — saneo ~900 LOC muertas; **PT-22** (v2) — editor catálogo/prompts con eval obligatorio.

## Lo que queda fuera del alcance (y por qué)

- **Análisis y reportes.** Todo lo que sea mirar, cruzar o reportar el atributo
  tipo vive aguas abajo ([[SNI Intelligence]]). Duplicarlo aquí rompería el modelo
  hub-and-spoke. **Excepción ([[DECISIONES#D-19 · ProjectType gana loop humano propio (UI de validación/clasificación manual)|D-19]]):** la UI de **validación y clasificación manual** del propio atributo SÍ entra — es tooling interno del enriquecedor (cola HITL, picker de tipos, clasificar pendientes), no reportería ni dashboards de cartera.
- **Hablar con otros repos directamente.** La comunicación es SOLO vía el
  store; el único código compartido es sni-commons.
- **Elegir proveedor LLM definitivo.** Decisión ministerial pendiente; la
  postura del repo es neutralidad (cualquier backend de `sni_commons.llm`).
- **Versionar datos.** Ni el store, ni CSV, ni `.duckdb` entran al repo, nunca.
- **Editor de catálogo/prompts en v1.** Diferido a PT-22 (v2) con eval
  obligatorio antes/después de cada cambio.

## Cómo encaja en el ecosistema (de quién depende, quién depende de él)

**Depende de:**
- **El store canónico** (`~/bip_data`, DuckDB) — lee `CONSULTAS_EBI` cargada
  por `bip-data load` desde las planillas que llegan por correo.
- **sni-commons** — cliente LLM unificado (`llm`), contrato
  `ENR_TIPO_PROYECTO_CONTRACT` (`contracts`), `BipDataStore` (`store`) y el
  mapeo claves→nombres de sector/subsector (`reference`).

**Dependen de él:**
- **SNI Intelligence** — consume `enr_tipo_proyecto` para filtrar por tipo
  (`--filter tipo_proyecto=…`) y, aguas abajo, para seleccionar los proyectos
  cuya carpeta digital baja BIP CD y verifica RAG. El atributo que este repo
  crea es el primer eslabón de ese caso de uso estrella.

```
planillas EBI ──bip-data──► store (CONSULTAS_EBI)
                              │ lee                    ▲ escribe
                              ▼                        │
                         ProjectType ── enr_tipo_proyecto
                              │
                              ▼ consume
                      SNI Intelligence (filtra por tipo) ──► BIP CD ──► RAG
```
