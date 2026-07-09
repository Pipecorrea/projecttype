# Estructura del proyecto

```
ProjectType/
├── data/
│   ├── raw/              # Datos de entrada (BIP, submuestra etiquetada)
│   ├── taxonomy/         # Taxonomía de tipos de proyecto (YAML, CSV, JSON)
│   └── output/           # Resultados del clasificador y revisiones
├── docs/                 # Documentación del proyecto
├── scripts/              # CLIs ejecutables
├── src/projecttype/      # Paquete Python
└── tests/                # Tests unitarios
```

## Scripts

| Comando | Descripción |
|---------|-------------|
| `python scripts/classify_l1.py` | Clasifica proyectos con Nivel 1 (keywords) |
| `python scripts/classify_cascade.py` | Cascada L1 → L2 (keywords + embeddings) |
| `python scripts/classify_cascade.py --enable-l3` | Cascada L1 → L2 → L3 con **Ollama local** (default) |
| `python scripts/classify_cascade.py --enable-l3 --l3-model llama3.2` | L3 con modelo Ollama específico |
| `python scripts/classify_cascade.py --list-ollama-models` | Lista modelos instalados en Ollama |
| `python scripts/classify_cascade.py --enable-l3 --l3-provider openai` | L3 con OpenAI (requiere `OPENAI_API_KEY`) |
| `python scripts/build_few_shot_examples.py` | Genera few-shot desde manual (L1 falló) |
| `python scripts/export_l3_prompts.py -n 10` | Exporta prompts L3 de muestra para revisión |
| `python scripts/classify_cascade.py --enable-l3 --l3-limit 100` | Piloto L3 con avance en consola |
| `python scripts/calibrate_l2.py` | Calibra umbrales L2 vs etiquetado manual |
| `python scripts/analyze_l2_sector.py` | Análisis L2 por sector (ayuda vs empeora) |
| `python scripts/build_revision_manual.py` | Genera Excel de revisión L1 vs manual |
| `python scripts/export_composites.py` | Exporta índice de tipos compuestos por subsector |

## Archivos clave

| Ruta | Contenido |
|------|-----------|
| `data/raw/base_datos_extracto.csv` | Extracto BIP para clasificar |
| `data/raw/Submuestra_tp.xlsx` | Submuestra con tipo de proyecto manual |
| `data/taxonomy/taxonomia_tipos_proyecto.yaml` | Taxonomía canónica del clasificador |
| `data/taxonomy/composites_index.csv` | Tipos compuestos y subtipos detectados automáticamente |
| `data/output/resultados_l1.csv` | Salida del clasificador Nivel 1 |
| `data/output/resultados_l1_l2.csv` | Salida cascada L1 + L2 |
| `data/output/resultados_l1_l2_l3.csv` | Salida cascada L1 + L2 + L3 |
| `data/prompts/l3.yaml` | System prompt, CoT, rúbrica y casos borde (v2) |
| `data/prompts/few_shot_examples.yaml` | Ejemplos few-shot curados por dominio |
| `data/prompts/few_shot_mined.yaml` | Ejemplos few-shot minados desde submuestra |
| `data/output/l3_prompts_sample.jsonl` | Muestra de prompts exportados |
| `data/output/revision_manual_l1.xlsx` | Excel para revisión humana |

## Flujo de trabajo

1. Clasificar: `python scripts/classify_l1.py`
2. Revisar: `python scripts/build_revision_manual.py`
3. Abrir `data/output/revision_manual_l1.xlsx` y validar filas con **Discrepancia**
