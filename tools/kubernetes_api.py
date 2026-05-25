"""tools/kubernetes_api.py — Tool-calling a Kubernetes API."""
from __future__ import annotations
import os

K8S_AVAILABLE = bool(os.getenv("K8S_KUBECONFIG_PATH"))


async def fetch_pod_status(service: str) -> str:
    if not K8S_AVAILABLE:
        return _mock_pod_status(service)
    # TODO: usar kubernetes-client/python en producción
    return _mock_pod_status(service)


def _mock_pod_status(service: str) -> str:
    return (
        f"[MOCK] K8s pod status for {service}:\n"
        f"  {service}-7d9f8b-xk2p9  CrashLoopBackOff  5 restarts  (T-40min)\n"
        f"  {service}-7d9f8b-m3n7q  Running           0 restarts\n"
        f"  {service}-7d9f8b-p1l4r  Pending           Insufficient memory\n"
        f"  postgres-primary-0      NotReady          Liveness probe failed\n"
        f"  postgres-replica-0      Running           OK"
    )
