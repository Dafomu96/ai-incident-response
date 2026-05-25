# ADR-003 — Contextual Retrieval sobre RAG clásico

**Estado:** Aceptado  
**Fecha:** Mayo 2026  
**Autores:** David Font Muñoz

---

## Contexto

El sistema necesita recuperar runbooks operacionales y postmortems históricos relevantes para que el Agente 3 (Diagnostic Reasoner) pueda diagnosticar la causa raíz de un incidente. La calidad del retrieval impacta directamente en la precisión diagnóstica — un chunk recuperado irrelevante puede llevar al modelo a una hipótesis incorrecta.

La implementación inicial usaba RAG clásico: dividir el documento en chunks de 512 tokens, generar embeddings con sentence-transformers, y recuperar por similitud coseno. Durante las pruebas se detectó un problema sistemático.

---

## El problema con RAG clásico en runbooks operacionales

Los runbooks técnicos tienen una estructura jerárquica densa. Un chunk de 512 tokens extraído de la sección "Remediación" de un runbook de DB connection pool puede contener:

```
1. Verificar queries activas en PostgreSQL:
   SELECT pid, now() - pg_stat_activity.query_start AS duration
   FROM pg_stat_activity WHERE state != 'idle'
2. Matar queries bloqueadas > 60s
3. Si persiste: kubectl rollout restart deployment/payment-service
```

Este chunk, sin contexto, no indica qué servicio afecta, qué síntomas lo preceden, ni qué causa raíz trata. Al fragmentarse pierde el contexto del documento que le da significado. El embedding resultante es genérico — "restart kubernetes deployment" — y puede recuperarse para incidentes no relacionados.

El problema se amplifica en postmortems históricos, donde cada sección (timeline, causa raíz, lecciones aprendidas) tiene más valor cuando el modelo sabe que pertenece a un incidente específico de un servicio concreto.

---

## Decisión

**Contextual Retrieval** — técnica publicada por Anthropic en septiembre de 2024.

Antes de generar el embedding de cada chunk, se genera un contexto de 50-100 tokens con un LLM que describe qué parte del documento es ese chunk y por qué es relevante. El embedding se genera sobre `contexto + chunk`, no solo sobre el chunk.

```
[CONTEXTO GENERADO] Este chunk describe los pasos de remediación 
inmediata para DB connection pool exhaustion en servicios Python 
con PostgreSQL, específicamente cómo identificar y matar queries 
bloqueadas y cuándo hacer restart del servicio.

[CHUNK ORIGINAL] 1. Verificar queries activas en PostgreSQL:
SELECT pid, now() - pg_stat_activity.query_start...
```

---

## Implementación

```python
def _add_context_to_chunk(document: str, chunk: str) -> str:
    prompt = (
        f"<document>{document[:2000]}</document>\n"
        f"<chunk>{chunk}</chunk>\n"
        "In 1-2 sentences, explain what this chunk is about "
        "within the document context. Be specific."
    )
    response = llm.invoke([HumanMessage(content=prompt)])
    return f"{response.content}\n\n{chunk}"
```

El contexto se genera en ingesta (one-time por documento), no en retrieval. El coste adicional es puntual, no recurrente.

---

## Razones

**Mejora de precisión medida.** Según benchmarks publicados por Anthropic, Contextual Retrieval reduce los errores de retrieval hasta un 67% respecto a RAG clásico en documentos técnicos densos. Para runbooks operacionales, donde la especificidad del contexto es crítica, el impacto es especialmente relevante.

**Coste asumible.** El coste adicional se produce únicamente en ingesta — cuando se añade un nuevo runbook o postmortem a la base de conocimiento. En retrieval (cada vez que el Agente 3 consulta la RAG) no hay coste adicional. Una base de conocimiento de 50 runbooks con un promedio de 5 chunks cada uno requiere 250 llamadas adicionales al LLM en ingesta, que es un coste one-time amortizado indefinidamente.

**Impacto en diagnóstico.** Un chunk con contexto recuperado incorrectamente puede llevar al Agente 3 a una hipótesis equivocada que se propaga por todo el pipeline — remediación incorrecta, HITL innecesario, postmortem con causa raíz errónea. El coste de un falso diagnóstico en producción supera con creces el coste de la contextualización.

---

## Alternativas descartadas

**RAG clásico (chunk → embedding → retrieval).** Implementación inicial. Descartada por los problemas de contexto descritos arriba.

**HyDE (Hypothetical Document Embeddings).** Genera un documento hipotético para la query antes de buscar. Añade latencia en retrieval (no en ingesta) y requiere un LLM en cada búsqueda. No apropiado para un sistema donde el retrieval ocurre en tiempo real durante un incidente.

**Reranking únicamente.** Usar Cohere Rerank sobre los resultados del RAG clásico mejora el orden pero no soluciona el problema de fondo — chunks sin contexto siguen generando embeddings débiles. Cohere Rerank está implementado como capa adicional opcional sobre Contextual Retrieval, no como sustituto.

**Parent document retrieval.** Recuperar el documento completo en lugar de chunks. No escalable con runbooks largos — el contexto del LLM se llena rápidamente con documentos completos irrelevantes.

---

## Trade-offs asumidos

**Coste de ingesta.** Cada nuevo documento requiere N llamadas al LLM para contextualizar sus chunks (N = número de chunks). Con Claude Haiku en producción el coste es mínimo pero existe. Compensado por la mejora de precisión diagnóstica.

**Latencia de ingesta.** Ingestar un runbook de 3.000 palabras tarda ~30 segundos en lugar de ~2 segundos con RAG clásico. Aceptable porque la ingesta es una operación de mantenimiento, no de tiempo real.

**Dependencia de la calidad del contexto generado.** Si el LLM genera un contexto incorrecto o demasiado genérico, el embedding resultante puede ser peor que el del chunk solo. En la práctica esto es raro con Haiku/Groq para esta tarea específica, pero es un punto de fallo a monitorizar.

---

## Consecuencias

- Los 5 runbooks de ejemplo en `rag/seed_runbooks.py` se ingestan con Contextual Retrieval
- Los postmortems generados por el Agente 5 se ingestan automáticamente con Contextual Retrieval (loop de aprendizaje)
- El retrieval usa dense search + Cohere Rerank opcional como segunda capa de mejora
