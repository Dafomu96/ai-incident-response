# ADR-001 — LangGraph sobre crewAI y AutoGen

**Estado:** Aceptado  
**Fecha:** Mayo 2026  
**Autores:** David Font Muñoz

---

## Contexto

Al diseñar el sistema de incident response necesitábamos un framework de orquestación de agentes. Los tres candidatos evaluados fueron LangGraph, crewAI y AutoGen.

El sistema tiene un requisito fundamental que no es negociable: **el flujo no es lineal**. El Diagnostic Reasoner puede determinar que necesita más datos antes de dar un diagnóstico con suficiente confianza, lo que requiere volver al Data Collector con una ventana temporal ampliada. Esto es un loop condicional — el agente decide en tiempo de ejecución si avanzar o reintentar.

---

## Decisión

**LangGraph.**

---

## Razones

**crewAI** está optimizado para pipelines lineales con roles fijos: agente A pasa a agente B pasa a agente C. Internamente crewAI orquesta conversaciones entre agentes con roles predefinidos. No soporta loops condicionales de forma nativa — implementar "volver al Agente 2 si la confianza es baja" requeriría lógica custom que va contra el modelo mental del framework.

**AutoGen** tiene un modelo de conversación entre agentes (los agentes se "hablan" entre ellos) que introduce latencia innecesaria y complejidad conversacional para un sistema que necesita respuesta determinista en segundos. AutoGen está diseñado para tareas de razonamiento colaborativo, no para pipelines de incident response donde cada nodo tiene una responsabilidad clara y un output tipado.

**LangGraph** permite exactamente el patrón que necesita este sistema:

- **Grafo cíclico:** el edge condicional `route_after_diagnosis` puede devolver `data_collector` si `diagnosis.requires_more_data = True`, creando el loop de rediagnóstico de forma nativa
- **Estado tipado:** `IncidentState` (TypedDict) persiste en cada nodo y es accesible por todos los agentes sin pasar datos manualmente entre ellos
- **Checkpointing:** si el sistema cae a mitad de un incidente P1, el grafo retoma exactamente donde lo dejó gracias a `MemorySaver` (dev) o `SqliteSaver` (prod)
- **Edges condicionales explícitos:** `route_after_triage`, `route_after_diagnosis`, `route_after_planning` son funciones Python puras — completamente testeables con pytest sin necesidad de mocks de LLM
- **Nodo de error dedicado:** captura excepciones en cualquier punto del grafo sin dejar el estado inconsistente

---

## Alternativas descartadas

| Framework | Razón de descarte |
|---|---|
| crewAI | No soporta loops condicionales nativamente — pipeline lineal únicamente |
| AutoGen | Modelo conversacional introduce latencia y no-determinismo innecesarios |
| LangChain LCEL | Sin estado persistente entre nodos, sin checkpointing |
| Implementación custom | Reinventar checkpointing y estado distribuido es trabajo no diferenciador |

---

## Trade-offs asumidos

**Verbosidad.** LangGraph requiere definir explícitamente nodos, edges, y estado. El mismo pipeline en crewAI sería 30% menos código. Este coste es aceptable porque la verbosidad hace el flujo completamente auditable — cualquier ingeniería puede leer `workflow.py` y entender exactamente qué hace el sistema.

**Curva de aprendizaje.** LangGraph tiene conceptos más avanzados (StateGraph, conditional edges, interrupt) que crewAI. Para un equipo nuevo al framework, crewAI sería más rápido de onboardear. En el contexto de este proyecto, el control granular compensa este coste.

---

## Consecuencias

- Los 3 edges condicionales del grafo son funciones Python puras testeadas en `tests/test_state.py`
- El checkpointing permite recuperación ante fallos en incidentes P1 sin perder contexto
- El loop de rediagnóstico (Agente 3 → Agente 2 → Agente 3) funciona de forma nativa sin lógica custom
