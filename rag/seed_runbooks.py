"""
rag/seed_runbooks.py — Ingesta runbooks de ejemplo en ChromaDB.
Ejecutar una vez antes del primer test end-to-end:
  python -m rag.seed_runbooks
"""
from dotenv import load_dotenv
load_dotenv()

from rag.ingestion import ingest_runbook

RUNBOOKS = [
    {
        "doc_id": "runbook-db-pool-001",
        "title": "DB Connection Pool Exhaustion",
        "content": """
## Síntomas
- P99 latency > 500ms en servicios con acceso a base de datos
- Logs: ConnectionPoolExhaustedException, Failed to acquire connection
- Prometheus: db_pool_active_connections cerca del máximo configurado
- CrashLoopBackOff en pods del servicio afectado

## Causas habituales
1. Incremento súbito de tráfico sin autoescalado configurado
2. Query lenta bloqueando conexiones durante > 30s
3. Leak de conexiones por código que no cierra el cursor correctamente
4. Deploy reciente que introdujo una query N+1

## Diagnóstico
1. Verificar queries activas en PostgreSQL:
   SELECT pid, now() - pg_stat_activity.query_start AS duration, query, state
   FROM pg_stat_activity WHERE state != 'idle' ORDER BY duration DESC;
2. Revisar métricas de pool: db_pool_active_connections / db_pool_max_connections
3. Correlacionar con commits recientes: git log --oneline -10

## Remediación
### Inmediata (LOW risk — auto-ejecutable)
- Matar queries bloqueadas > 60s: SELECT pg_terminate_backend(pid) WHERE duration > '60s'
- Restart del servicio afectado: kubectl rollout restart deployment/<service>

### Si persiste (HIGH risk — requiere aprobación)
- Rollback al deploy anterior: kubectl rollout undo deployment/<service>
- Escalar réplicas de lectura de la base de datos

## Prevención
- Alertar cuando db_pool_active_connections > 80% del máximo
- Añadir query timeout de 30s en la configuración del ORM
- Revisar EXPLAIN ANALYZE en queries nuevas antes de deploy
        """,
    },
    {
        "doc_id": "runbook-memory-leak-001",
        "title": "Memory Leak — OOMKilled Pods",
        "content": """
## Síntomas
- Pods en estado OOMKilled en kubectl get pods
- Memoria creciente sin liberación: container_memory_usage_bytes en tendencia ascendente
- Reinicios frecuentes del pod (> 3 en 1 hora)
- Degradación gradual de latencia antes del crash

## Causas habituales
1. Leak en código: objetos en memoria no liberados (listas crecientes, caches sin TTL)
2. Deploy reciente con nueva dependencia que tiene leak conocido
3. Límite de memoria del pod demasiado bajo para el workload actual
4. Procesamiento de payloads grandes sin streaming

## Diagnóstico
1. Revisar tendencia de memoria: container_memory_usage_bytes{container="<service>"}[1h]
2. Identificar el pod con más reinicios: kubectl get pods --sort-by='.status.containerStatuses[0].restartCount'
3. Ver logs del pod antes del OOM: kubectl logs <pod> --previous
4. Correlacionar con commits: cambios en dependencias o en código de procesamiento

## Remediación
### Inmediata (LOW risk)
- Restart del deployment para liberar memoria acumulada
- Reducir temporalmente el número de workers/threads

### Correctiva (HIGH risk)
- Rollback si el leak coincide con un deploy reciente
- Aumentar memory limit del pod: editar resources.limits.memory

## Prevención
- Alertar cuando memory_usage > 85% del límite durante > 10 minutos
- Añadir profiling de memoria en entorno de staging antes de deploy
        """,
    },
    {
        "doc_id": "runbook-high-error-rate-001",
        "title": "High Error Rate — 5xx Responses",
        "content": """
## Síntomas
- Error rate > 5%: sum(rate(http_requests_total{status=~"5.."}[5m])) / sum(rate(http_requests_total[5m]))
- Alertas de PagerDuty por SLO de disponibilidad
- Usuarios reportando errores en la aplicación

## Causas habituales
1. Dependencia downstream no disponible (base de datos, servicio externo, cache)
2. Deploy con bug que provoca excepciones no controladas
3. Certificado SSL expirado en comunicación entre servicios
4. Rate limiting de una API externa alcanzado

## Diagnóstico
1. Identificar el endpoint con más errores:
   sum by (path) (rate(http_requests_total{status=~"5.."}[5m]))
2. Revisar logs de errores: buscar stack traces en Loki
3. Comprobar dependencias: health checks de servicios downstream
4. Verificar commits recientes en el servicio afectado

## Remediación
### Inmediata (LOW risk)
- Clear cache si los errores están relacionados con datos corruptos en cache
- Restart del servicio si los errores empezaron con el último deploy

### Si es dependencia downstream (variable)
- Activar circuit breaker si no está activo
- Redirigir tráfico a réplica sana si existe

### Deploy con bug (HIGH risk)
- Rollback inmediato: kubectl rollout undo deployment/<service>

## Prevención
- SLO alert: error_rate > 1% durante > 5 minutos
- Smoke tests automáticos post-deploy
- Health checks con timeout en todas las dependencias
        """,
    },
    {
        "doc_id": "runbook-disk-full-001",
        "title": "Disk Full — Pod o Nodo",
        "content": """
## Síntomas
- Alertas de node_filesystem_avail_bytes < 10%
- Pods fallando al escribir logs o datos temporales
- Errores: No space left on device en logs

## Causas habituales
1. Logs no rotados acumulándose
2. Archivos temporales de jobs batch no limpiados
3. Imágenes Docker antiguas en el nodo
4. Base de datos sin política de retención configurada

## Diagnóstico
1. Identificar qué ocupa el espacio: du -sh /* 2>/dev/null | sort -rh | head -20
2. Ver logs más grandes: find /var/log -size +100M
3. Espacio ocupado por Docker: docker system df

## Remediación
### Inmediata (LOW risk)
- Limpiar imágenes Docker no usadas: docker image prune -a
- Rotar y comprimir logs antiguos: logrotate -f /etc/logrotate.conf
- Limpiar archivos temporales: find /tmp -mtime +1 -delete

### Si persiste (HIGH risk)
- Expandir el volumen del nodo (requiere aprobación)
- Migrar pods a otro nodo con más espacio disponible

## Prevención
- Alertar cuando disco > 80% de uso
- Configurar log rotation automático
- Política de retención en base de datos (borrar registros > 90 días)
        """,
    },
    {
        "doc_id": "runbook-network-latency-001",
        "title": "Network Latency Between Services",
        "content": """
## Síntomas
- Latencia elevada en llamadas entre microservicios (> 200ms p99 interno)
- Timeouts intermitentes en comunicación entre pods
- Métricas normales en cada servicio individualmente pero degradación end-to-end

## Causas habituales
1. Problema en el CNI (Container Network Interface) del cluster
2. Nodo con alta carga de CPU que afecta al networking
3. Misconfiguration en network policies de Kubernetes
4. DNS resolution lenta (CoreDNS sobrecargado)

## Diagnóstico
1. Medir latencia entre pods: kubectl exec <pod> -- curl -w "%{time_total}" <service>
2. Revisar estado de CoreDNS: kubectl get pods -n kube-system | grep coredns
3. Comprobar network policies: kubectl get networkpolicies --all-namespaces
4. CPU del nodo: node_cpu_usage_seconds_total

## Remediación
### Inmediata (LOW risk)
- Restart de CoreDNS si está degradado: kubectl rollout restart deployment/coredns -n kube-system
- Mover pods afectados a otro nodo: kubectl drain <node> --ignore-daemonsets

### Si es network policy (HIGH risk)
- Revisar y corregir network policies (requiere aprobación de seguridad)

## Prevención
- Monitorizar latencia inter-servicio con métricas de service mesh
- Alertar cuando CoreDNS response time > 50ms
        """,
    },
]


def main():
    print(f"Ingestando {len(RUNBOOKS)} runbooks en ChromaDB...")
    for rb in RUNBOOKS:
        ingest_runbook(
            title=rb["title"],
            content=rb["content"],
            doc_id=rb["doc_id"],
        )
    print(f"\nListo. ChromaDB lista para el Diagnostic Reasoner.")


if __name__ == "__main__":
    main()
