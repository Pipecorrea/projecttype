"""Loop humano (HITL) de ProjectType — cola de revisión y clasificación manual.

Herramienta interna del enriquecedor (D-19), no reportería. El server es
read-only sobre el store; las escrituras al store van solo por `store_publish`
+ gate (D-13 intacto). Los veredictos humanos persisten en JSONL commiteado
(política de datos derivados).
"""
