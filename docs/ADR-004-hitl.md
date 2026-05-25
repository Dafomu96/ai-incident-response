# ADR-004 — Human-in-the-Loop por tipo de acción, no por severidad

**Estado:** Aceptado  
**Fecha:** Mayo 2026  
**Autores:** David Font Muñoz

---

## Contexto

El sistema necesita decidir cuándo una acción de remediación requiere aprobación humana antes de ejecutarse. La pregunta de diseño es: ¿cuál es la variable que determina si una acción necesita supervisión humana?

Dos enfoques posibles:

1. **Por severidad del incidente:** P1 y P2 requieren aprobación, P3 no.
2. **Por riesgo de la acción específica:** acciones reversibles de bajo impacto se ejecutan automáticamente, acciones destructivas o difícilmente reversibles requieren aprobación.

---

## Decisión

**Matriz de permisos por tipo de acción, independientemente de la severidad del incidente.**

```
ActionRisk.LOW  → auto-ejecutable
ActionRisk.HIGH → HITLRequest → Slack → aprobación humana
```

---

## Razones

**HITL por severidad es incoherente con el objetivo de automatización.**

Si un incidente P1 tiene como solución reiniciar un pod (operación reversible en 30 segundos), esperar aprobación humana añade minutos de downtime sin ningún beneficio. El pod se reinicia igualmente — la única diferencia es que el sistema de producción ha estado caído más tiempo.

Si un incidente P2 tiene como solución un rollback de deployment (operación que puede introducir regresiones y afecta a todos los usuarios), ejecutarlo automáticamente sin aprobación es arriesgado aunque la severidad sea "solo P2".

La severidad describe el impacto del incidente. El riesgo de la acción describe el impacto de la remediación. Son dimensiones ortogonales.

**La variable correcta es la reversibilidad y el blast radius de la acción.**

Acciones `LOW risk` (auto-ejecutables):
- `kubectl rollout restart deployment/<service>` — reversible, impacto localizado al servicio
- `kubectl exec -- redis-cli FLUSHDB` — reversible con coste mínimo (regeneración de cache)
- `kubectl scale deployment/<service> --replicas=N` — reversible inmediatamente
- `kubectl exec -- logrotate -f` — sin impacto en servicio

Acciones `HIGH risk` (requieren aprobación):
- `kubectl rollout undo deployment/<service>` — rollback puede introducir regresiones
- `kubectl delete pvc/<volume>` — pérdida de datos potencial
- modificar network policies — impacto en seguridad y conectividad de múltiples servicios
- escalar infraestructura — coste económico inmediato

---

## Implementación

El Agente 4 (Remediation Planner) clasifica cada acción al generarla:

```python
class ActionRisk(str, Enum):
    LOW = "low"   # auto-ejecutable
    HIGH = "high" # requiere aprobación humana
```

Para acciones HIGH, genera un `HITLRequest` con contexto completo:
- Descripción de la acción y comando exacto a ejecutar
- Resumen del diagnóstico con confianza del Agente 3
- Timeout de 10 minutos con escalado automático si no hay respuesta

El mensaje se envía al canal `#incident-approvals` en Slack con botones **Approve** y **Reject**. El ingeniero de guardia toma la decisión con el contexto completo visible — no necesita buscar información adicional para aprobar o rechazar.

---

## Timeout y escalado automático

Si no hay respuesta en 10 minutos (configurable via `HITLRequest.timeout_minutes`), el sistema escala automáticamente. En la implementación actual esto significa continuar con la ejecución — en producción podría significar notificar a un nivel superior de on-call.

El timeout previene que el sistema quede bloqueado indefinidamente esperando una aprobación que no llega (ingeniero dormido, Slack caído, etc.). Un incidente P1 no puede esperar indefinidamente.

---

## Log de auditoría

Todas las decisiones — aprobadas, rechazadas, y auto-ejecutadas — quedan registradas en el `IncidentState` del grafo y trazadas en LangSmith. Esto permite:

- Post-incident review: qué aprobó quién y cuándo
- Identificar acciones clasificadas incorrectamente como LOW que deberían ser HIGH
- Medir el tiempo entre envío del HITLRequest y aprobación (tiempo de respuesta del on-call)

---

## Alternativas descartadas

**HITL para todas las acciones.** Elimina el beneficio de automatización. Si cada acción requiere aprobación humana, el sistema es un generador de recomendaciones, no un agente autónomo. El tiempo de resolución sería similar al proceso manual actual.

**HITL por severidad (P1/P2 sí, P3 no).** Incoherente — un P3 con acción de rollback es más arriesgado que un P1 con acción de restart. Ver razonamiento principal arriba.

**Sin HITL (fully autonomous).** Inaceptable para acciones con riesgo de pérdida de datos o impacto en seguridad. En producción real, un sistema que ejecuta rollbacks automáticamente sin supervisión humana generaría desconfianza operacional independientemente de su tasa de acierto.

**HITL basado en confianza del diagnóstico.** Si la confianza del Agente 3 es < 80%, requerir aprobación. Descartado porque mezcla la incertidumbre del diagnóstico con el riesgo de la acción — son problemas distintos. Una acción de restart es segura aunque el diagnóstico tenga 60% de confianza. Un rollback es arriesgado aunque el diagnóstico tenga 99% de confianza.

---

## Trade-offs asumidos

**La clasificación LOW/HIGH del Agente 4 puede ser incorrecta.** El LLM puede clasificar una acción arriesgada como LOW en casos edge. El log de auditoría permite identificar estos casos y mejorar el prompt del Agente 4. El riesgo se mitiga con el principio de que en caso de duda el Agente 4 debe clasificar HIGH.

**Dependencia de disponibilidad de Slack.** Si Slack no está disponible, el HITL no puede completarse. En producción esto requiere un canal de fallback (PagerDuty, email, SMS). En la implementación actual el timeout garantiza que el sistema no queda bloqueado indefinidamente.
