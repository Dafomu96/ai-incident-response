# ADR-002 — Selección de modelos LLM por tipo de tarea

**Estado:** Aceptado  
**Fecha:** Mayo 2026  
**Autores:** David Font Muñoz

---

## Contexto

El sistema tiene 5 agentes con necesidades muy distintas en términos de latencia, capacidad de razonamiento y coste. La decisión más simple sería usar un único modelo para todos los agentes, pero esto implica un trade-off negativo en alguna de las tres dimensiones para cada agente.

Las restricciones del sistema son:

- **Agente 1 (Triage):** debe clasificar la severidad en menos de 500ms. Es el entry point del sistema y cualquier latencia aquí se percibe directamente como tiempo de respuesta del sistema.
- **Agentes 3, 4, 5:** necesitan razonamiento profundo, chain-of-thought fiable, y structured outputs que pasen validación estricta de Pydantic v2 en el primer intento.
- **RAG contextualización:** se genera un contexto de 50-100 tokens por cada chunk en ingesta. Con documentos de varios miles de tokens y chunks de 512 tokens, una sola ingesta puede requerir decenas de llamadas. El coste se acumula rápidamente.
- **Resiliencia:** el sistema no puede depender de un único proveedor de LLM.

---

## Decisión

**Tres modelos distintos según el tipo de tarea, con fallback global.**

| Agente | Modelo (desarrollo) | Modelo (producción) | Criterio |
|---|---|---|---|
| Agente 1 — Triage | Groq Llama 3.3 70B | Groq Llama 3.3 70B | Latencia <500ms |
| Agentes 3/4/5 | Groq Llama 3.3 70B | Claude Sonnet | Razonamiento profundo |
| RAG contextualización | Groq Llama 3.3 70B | Claude Haiku | Coste mínimo por chunk |
| Fallback global | GPT-4o | GPT-4o | Resiliencia |

---

## Razones por modelo

### Groq Llama 3.3 70B — Agente 1 (siempre)

El Agente 1 realiza una clasificación binaria con criterios explícitos (P1/P2/P3) sobre un input estructurado. No necesita razonamiento profundo — necesita velocidad. Groq con Llama 3.3 70B responde en ~300ms gracias a su hardware especializado (LPU), muy por debajo del objetivo de 500ms. Claude Sonnet tiene una latencia media de 1-3 segundos en respuestas estructuradas, inaceptable para el entry point de un sistema de incident response donde cada segundo cuenta.

### Claude Sonnet — Agentes 3, 4, 5 (producción)

El Agente 3 (Diagnostic Reasoner) es el core del sistema. Debe correlacionar logs, métricas, commits y estado de pods, consultarlos contra runbooks históricos via RAG, y generar hipótesis ordenadas por probabilidad con evidencias. Este es exactamente el tipo de tarea donde Claude Sonnet supera a modelos más pequeños: razonamiento multi-paso, chain-of-thought coherente, y fidelidad en structured outputs complejos.

En evaluaciones internas, Llama 3.3 70B tiende a anclar el diagnóstico en la señal más obvia de los datos (el commit de postgres driver en el mock) ignorando señales secundarias. Claude Sonnet integra mejor evidencias contradictorias y produce hipótesis más matizadas.

Los structured outputs con Pydantic v2 son más fiables con Claude Sonnet — menos errores de parsing que requieren retry, lo que reduce la latencia total del pipeline.

### Claude Haiku — RAG contextualización (producción)

La contextualización de chunks (Contextual Retrieval) requiere una llamada por chunk para generar 50-100 tokens de contexto. Esta tarea es simple: "describe qué parte del documento es este chunk". No necesita razonamiento profundo. Claude Haiku a un coste ~20x menor que Sonnet es la elección obvia. El ahorro es significativo en ingesta de bases de conocimiento grandes.

### GPT-4o — Fallback global

Si la API de Anthropic no está disponible, el sistema cae automáticamente a GPT-4o mediante retry logic con tenacity. Esto garantiza continuidad del servicio en incidentes P1 donde no se puede esperar a que se restaure un proveedor.

---

## Desarrollo vs producción

Durante el desarrollo, todos los agentes usan Groq Llama 3.3 70B por coste cero en el free tier. Esto introduce un sesgo conocido en las evaluaciones — el modelo tiende a diagnosticar "postgres driver update" independientemente del tipo de incidente cuando las señales son ambiguas.

Los resultados de evaluación con Groq (Top-3 accuracy: 62%) son el baseline de desarrollo. Con Claude Sonnet en producción se esperan mejoras significativas en los casos donde la causa raíz requiere integrar señales de múltiples fuentes sin una señal dominante clara.

Esta distinción dev/prod es deliberada y documentada — no es una limitación oculta del sistema.

---

## Alternativas descartadas

**Un único modelo para todo.** Si se elige Claude Sonnet para todo, el Agente 1 tiene latencia >1s — inaceptable. Si se elige Groq para todo, los Agentes 3/4/5 tienen peor precisión diagnóstica en casos complejos. La selección por tarea es el único enfoque que optimiza las tres dimensiones simultáneamente.

**Mixtral 8x7B.** Evaluado como alternativa a Llama 3.3 70B para el Agente 1. Latencia similar pero peor calidad de structured outputs. Descartado.

**GPT-4o como modelo principal.** Latencia y coste superiores a Claude Sonnet sin ventaja clara en las tareas específicas del sistema. Mantenido como fallback por su disponibilidad y fiabilidad.

---

## Trade-offs asumidos

**Complejidad operacional.** Múltiples API keys, múltiples configuraciones, múltiples puntos de fallo. Compensado por la optimización coste-latencia-calidad por tarea y por la resiliencia del fallback.

**Inconsistencia dev/prod.** Los resultados de evaluación en desarrollo no son directamente comparables con los de producción. Documentado explícitamente en el README y en las evaluaciones.
