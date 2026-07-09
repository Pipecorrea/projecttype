---
tipo: vision
ambito: ProjectType
actualizado: 2026-07-06
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
- ✅ **Calidad de ingeniería.** 56 tests pytest (PT-8), mypy `--strict`, ruff —
  los tres bloqueantes en CI.
- 🧪 **Evaluación contra submuestra manual.** `evaluation.py` + scripts de
  calibración (L2) y revisión (Excel) existen y se usaron para calibrar
  umbrales, pero no corren en CI ni tienen formato común de golden-set: es
  herramienta de desarrollo, no control de regresión.
- 🔜 **Clasificación incremental (PT-7).** Hoy cada corrida completa
  re-clasifica los ~9.4k proyectos (el caché L3 evita re-pagar el LLM, pero el
  publish es de corrida completa). Lo incremental está diseñado, no construido.

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

1. **PT-7 — incremental** (la brecha principal): `enrich --incremental` que
   salte BIP ya clasificados, con publish parcial que no marque el resto como
   ausente (coordinado con sni-commons). Es el prerrequisito para colgarse de
   `eco refresh`.
2. **Versionar la inferencia en el dato**: añadir taxonomía/modelo/prompt como
   metadato al escribir (hoy solo va `enricher_version` y el ledger del store).
3. **Golden-set formal**: pasar la submuestra de `data/raw/Submuestra_tp.xlsx`
   + `evaluation.py` al formato común de evaluación del ecosistema; stub en CI,
   corrida real programada con presupuesto.
4. **Cobertura de taxonomía**: los tipos que el negocio pida y no existan se
   agregan editando el YAML — trabajo de dominio continuo, no de pipeline.
   (Ej. ya cubierto: "ciclovía" → `CICLOVIAS URBANAS`.)

## Lo que queda fuera del alcance (y por qué)

- **UI, análisis y reportes.** ProjectType es un enriquecedor **puro**:
  clasifica y publica. Todo lo que sea mirar, cruzar o reportar el atributo
  vive aguas abajo (SNI Intelligence). Duplicarlo aquí rompería el modelo
  hub-and-spoke.
- **Hablar con otros repos directamente.** La comunicación es SOLO vía el
  store; el único código compartido es sni-commons.
- **Elegir proveedor LLM definitivo.** Decisión ministerial pendiente; la
  postura del repo es neutralidad (cualquier backend de `sni_commons.llm`).
- **Versionar datos.** Ni el store, ni CSV, ni `.duckdb` entran al repo, nunca.

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
