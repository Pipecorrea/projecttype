# Auditoría manual — 13 casos L3 puro (dev, N=100)

`actualizado: 2026-07-10` · contexto: eval `eval_20260710T005731_gemini-2.5-flash.json` (91,5% exact match)

## Criterios

| Etiqueta | Significado |
|---|---|
| **multi_real** | ≥2 tipos con evidencia fuerte; golden eligió uno solo |
| **label_error** | Etiqueta manual genérica o no refleja obra dominante |
| **prompt_fix** | Manual defendible; modelo eligió variante incorrecta |

## Resumen

| Clasificación | N | % |
|---|---|---|
| multi_real | 9 | 69% |
| prompt_fix | 2–3 | 15–23% |
| label_error | 2 | 15% |

**Implicación PT-24:** la mayoría de “errores” son proyectos integrales (PMIB/saneamiento) con etiqueta única ex post. Multi-tipo + métrica **multi-hit** es el siguiente paso correcto.

## Casos

### Discrepancias asignadas (7)

| BIP | Manual → Predicho | Clasificación |
|---|---|---|
| 20145656 | Casetas…/AP → Red+Planta | multi_real |
| 20150130 | Casetas…/AP → Casetas…/Planta | multi_real + prompt_fix |
| 20177609 | Otros Deporte → Estadio Fútbol Amateur | label_error |
| 20182393 | Red AP+Alcant. → Casetas…/Energía | multi_real |
| 20188809 | Casetas…/AP → Red+Planta | multi_real |
| 20191836 | Casetas…/Energía → Red+Planta | label_error |
| 20192035 | Puente Urbano → Vías Estructurantes | multi_real |

### Ambiguos / sin_match (6)

| BIP | Manual → Predicho | Clasificación |
|---|---|---|
| 20116978 | Casetas…/AP → Red+Planta | multi_real |
| 20137860 | Colegio Básica/Media → Internado | multi_real |
| 20156686 | Casetas…/AP → Casetas…/Planta | prompt_fix |
| 20191865 | Casetas…/Energía → Red+Planta | multi_real |
| 20192885 | Casetas…/Energía → Casetas…/Planta | prompt_fix |
| 30002482 | Casetas…/AP → Red+Planta | multi_real |

## Siguiente paso

Re-evaluar estos 13 con `--l3-pure 100` y reportar `multi_hit_l3_puro` tras PT-24.
