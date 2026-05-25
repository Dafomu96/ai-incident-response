# ADR-005 — Evaluación custom con LangSmith sobre RAGAS

**Estado:** Aceptado  
**Fecha:** Mayo 2026  
**Autores:** David Font Muñoz

---

## Contexto

Evaluar un sistema RAG agéntico requiere medir dos cosas distintas: la calidad del retrieval (¿se recuperan los chunks correctos?) y la calidad del output final (¿el diagnóstico es correcto?). RAGAS es el framework estándar del ecosistema LangChain para esto.

Durante el diseño del sistema de evaluación se valoraron RAGAS y una implementación custom con LangSmith.

---

## El problema con RAGAS en este contexto

RAGAS tiene tres problemas concretos para este proyecto:

**Conflicto de dependencias.** RAGAS requiere versiones específicas de `datasets` y `langchain` que son incompatibles con LangGraph 0.2+ en Python 3.11. El conflicto se manifiesta en tiempo de instalación y no tiene solución limpia sin degradar alguna de las dos librerías. En un sistema de producción, forzar versiones incompatibles para satisfacer una librería de evaluación es inaceptable.

**Coste por evaluación.** Las métricas principales de RAGAS (faithfulness, answer relevancy, context precision) requieren llamadas adicionales a un LLM por cada evaluación. Evaluar 8 incidentes con RAGAS generaría ~40-60 llamadas adicionales al LLM además de las del pipeline principal. Con un límite de 100k tokens/día en el free tier de Groq, esto consume un porcentaje significativo del presupuesto diario.

**Métricas abstractas vs métricas de negocio.** Faithfulness mide si el output del LLM está soportado por el contexto recuperado. Context precision mide si los chunks recuperados son relevantes para la query. Estas métricas son útiles para sistemas RAG de Q&A general, pero para un sistema de incident response la métrica que importa es: **¿el sistema diagnosticó correctamente la causa raíz?** Esta pregunta solo se puede responder con ground truth real, no con métricas proxy.

---

## Decisión

**Evaluación directa contra ground truth histórico con LangSmith y métricas custom.**

---

## Dataset de ground truth

`evals/datasets/historical_incidents.json` contiene 8 incidentes reales con:

```json
{
  "alert_id": "hist-001",
  "alert": { ... },
  "ground_truth": {
    "severity": "P2",
    "root_cause": "DB connection pool exhaustion due to slow query after index drop",
    "root_cause_keywords": ["connection pool", "database", "postgres", "query", "driver"],
    "correct_actions": ["kill_blocking_queries", "recreate_index", "restart_service"]
  }
}
```

El ground truth incluye la causa raíz textual, keywords que deben aparecer en el diagnóstico, y las acciones de remediación correctas.

---

## Métricas implementadas

**Keyword overlap score.** Mide qué fracción de las keywords del ground truth aparecen en la hipótesis top-1 del Agente 3. Simple, determinista, sin llamadas adicionales al LLM.

```python
def keyword_overlap_score(hypothesis: str, keywords: list[str]) -> float:
    hypothesis_lower = hypothesis.lower()
    matches = sum(1 for kw in keywords if kw.lower() in hypothesis_lower)
    return matches / len(keywords)
```

**Top-1 accuracy.** La hipótesis más probable del Agente 3 supera el umbral de keyword overlap (0.25).

**Top-3 accuracy.** Al menos una de las 3 primeras hipótesis supera el umbral. Más permisiva — mide si el sistema considera la causa raíz correcta aunque no sea la primera.

**Severity accuracy.** La severidad clasificada por el Agente 1 coincide con el ground truth.

**Métricas de sistema.** HITL trigger rate (qué porcentaje de incidentes generan una aprobación humana), postmortem rate (siempre 100% si el pipeline completa), avg diagnosis attempts (indica si el loop de rediagnóstico se activa).

---

## Resultados actuales

Evaluación sobre 8 incidentes con Groq Llama 3.3 70B (modelo de desarrollo):

| Métrica | Resultado |
|---|---|
| Severity accuracy | 62% |
| Top-1 accuracy | 38% |
| Top-3 accuracy | 62% |
| Avg keyword score | 23% |
| HITL trigger rate | 100% |
| Postmortem rate | 100% |

**Análisis honesto de los resultados:** el modelo de desarrollo (Groq Llama 3.3 70B) tiene un sesgo conocido hacia "postgres driver update" como causa raíz en incidentes con señales ambiguas, porque los datos mock de GitHub siempre incluyen un commit de postgres driver. En incidentes con señales claras y específicas (N+1 query en inventory-service, Elasticsearch node failure en search-service) el Top-1 es correcto. Con Claude Sonnet en producción y datos reales de cada servicio se esperan mejoras significativas en los casos edge.

---

## LangSmith como plataforma de observabilidad

Todas las ejecuciones de evaluación se trazan en LangSmith con:

- Input completo de cada nodo (alert, logs, métricas, commits)
- Output de cada agente (IncidentReport, DiagnosisResult, RemediationPlan, PostmortemDraft)
- Token usage y latencia por agente
- Comparación entre ejecuciones para detectar regresiones

Esto permite hacer A/B testing entre versiones del Diagnostic Reasoner — cambiar el prompt, el modelo, o la estrategia de retrieval y comparar resultados en el mismo dataset de ground truth.

---

## Alternativas descartadas

**RAGAS.** Descartado por los tres problemas descritos arriba: conflicto de dependencias, coste por evaluación, y métricas abstractas que no responden la pregunta de negocio.

**Evaluación manual.** Leer los outputs del Agente 3 y juzgar si son correctos. No escalable, no reproducible, no automatizable en CI/CD.

**LLM-as-judge.** Usar un LLM para evaluar si el diagnóstico es correcto comparándolo con el ground truth. Añade coste y no-determinismo. Apropiado cuando no hay ground truth estructurado — en este caso sí lo hay.

---

## Trade-offs asumidos

**Keyword overlap es una métrica imperfecta.** Un diagnóstico correcto formulado con sinónimos puede puntuar 0%. Un diagnóstico incorrecto que menciona casualmente las keywords puede puntuar alto. Para mitigar esto se usa Top-3 accuracy además de Top-1, y el threshold se calibró empíricamente (0.25) para minimizar falsos negativos.

**El dataset de 8 incidentes es pequeño.** No es estadísticamente representativo. El objetivo es tener un baseline reproducible para detectar regresiones entre versiones, no medir la precisión absoluta del sistema. Para un dataset de evaluación robusto en producción se necesitarían 50-100 incidentes históricos reales.
