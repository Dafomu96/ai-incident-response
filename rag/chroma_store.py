"""rag/chroma_store.py — ChromaDB singleton."""
from __future__ import annotations
import os
import chromadb
from chromadb.config import Settings

_client: chromadb.ClientAPI | None = None


def get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        persist_dir = os.getenv("CHROMA_PERSIST_DIR", "./chroma_db")
        _client = chromadb.PersistentClient(
            path=persist_dir,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def get_collection(name: str = "runbooks") -> chromadb.Collection:
    return get_client().get_or_create_collection(name=name, metadata={"hnsw:space": "cosine"})
