# Artefactos de evaluación — ProjectType

Salidas versionadas del gate CI y corridas locales (`scripts/eval_golden.py`).

| Archivo | Rol |
|---|---|
| `baseline_pt17.json` | Métricas L1+L2 al cerrar PT-17 (golden expost n=2.357) |
| `golden_cobertura_subsector.csv` | Cobertura 47/84 subsectores (insumo UI HITL) |
| `confusion_*.csv` | Matriz confusión por estrato (`dev`, `holdout`, `expost`) |
| `eval_*.json` | Snapshots `ResultadoEval` por corrida (timestamp en nombre) |

## Golden dev/holdout (PT-23)

El golden `data/golden/golden_tipo_proyecto.jsonl` (v`2.1.0-expost-holdout`) etiqueta cada caso con `dev` o `holdout` (80/20 estratificado por subsector, semilla 42). Todos conservan el tag `expost`.

Regenerar:

```bash
uv run python scripts/convert_expost_to_golden.py
```

## Flujo de validación de prompts (sin publish al store)

**Iterar en dev** (puedes mirar confusión y ajustar YAML):

```bash
uv run python scripts/eval_golden.py --estrato dev --real
```

**Validar una vez en holdout** (no iterar mirando estos resultados):

```bash
uv run python scripts/eval_golden.py --estrato holdout --real
```

Piloto de costo L3 (default 30 llamadas con `--real`):

```bash
uv run python scripts/eval_golden.py --estrato dev --real
```

Evaluar todo el residual L3 del estrato:

```bash
uv run python scripts/eval_golden.py --estrato dev --real --full-l3
```

Backend L3: **Vertex** por defecto (`LLM_PROVIDER=gemini`, mismo mapa que OBSRATE).
Las llamadas L3 van en **paralelo** (`LLM_MAX_CONCURRENCY`, default 5 hilos).
Requiere `GOOGLE_CLOUD_PROJECT` + ADC (`gcloud auth application-default login`).
AI Studio solo con `LLM_PROVIDER=gemini-studio` + `GEMINI_API_KEY`.

**Gate CI** (solo L1+L2, L3 mock — no mide calidad de prompts):

```bash
uv run python scripts/eval_golden.py --ci
```

Métricas reportadas con `--real`:

- `precision_cascada` / `cobertura_cascada` — pipeline completo L1→L2→L3
- `precision_l3` / `cobertura_l3_residual` — solo asignaciones L3 sobre residual L1+L2

El publish a `enr_tipo_proyecto` queda **después** de que holdout sea aceptable.
