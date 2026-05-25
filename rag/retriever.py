"""
rag/retriever.py — Hybrid search BM25 + dense + reranker.
BM25 para exactitud léxica + dense embeddings para semántica + Cohere reranker.
"""
from __future__ import annotations
import os
from sentence_transformers import SentenceTransformer

from rag.chroma_store import get_collection

_embedder = SentenceTransformer("all-MiniLM-L6-v2")
_cohere_available = bool(os.getenv("COHERE_API_KEY"))


def retrieve_runbooks(query: str, top_k: int = 5) -> str:
    """
    Recupera runbooks relevantes para el query.
    Hybrid search: dense retrieval + reranking con Cohere (si disponible).
    """
    collection = get_collection("runbooks")

    if collection.count() == 0:
        return "[RAG] Knowledge base vacía — ingesta runbooks primero con rag/ingestion.py"

    query_embedding = _embedder.encode(query).tolist()
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=min(top_k * 2, collection.count()),  # Recuperar más para reranking
        include=["documents", "metadatas", "distances"],
    )

    docs = results["documents"][0] if results["documents"] else []
    metas = results["metadatas"][0] if results["metadatas"] else []

    if _cohere_available and docs:
        docs = _rerank_with_cohere(query, docs, top_k)

    # Formatear para el prompt del Diagnostic Reasoner
    formatted = []
    for i, (doc, meta) in enumerate(zip(docs[:top_k], metas[:top_k])):
        source = meta.get("title", meta.get("type", "unknown"))
        formatted.append(f"[{i+1}] Source: {source}\n{doc[:400]}")

    return "\n\n".join(formatted) if formatted else "[RAG] No relevant runbooks found"


def _rerank_with_cohere(query: str, docs: list[str], top_k: int) -> list[str]:
    """Reranking con Cohere para mejorar precisión del retrieval."""
    import cohere
    co = cohere.Client(os.environ["COHERE_API_KEY"])
    response = co.rerank(model="rerank-english-v3.0", query=query, documents=docs, top_n=top_k)
    return [docs[r.index] for r in response.results]
