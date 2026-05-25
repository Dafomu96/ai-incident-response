"""
graph/checkpointer.py — Configuración del checkpointer para persistencia.
En desarrollo: MemorySaver (in-memory).
En producción: SqliteSaver o PostgresSaver para persistencia real.
"""
from __future__ import annotations
import os

def get_checkpointer():
    """
    Retorna el checkpointer apropiado según el entorno.
    ENVIRONMENT=production -> SqliteSaver para persistencia entre reinicios.
    """
    env = os.getenv("ENVIRONMENT", "development")
    if env == "production":
        from langgraph.checkpoint.sqlite import SqliteSaver
        return SqliteSaver.from_conn_string("./checkpoints.db")
    else:
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()
