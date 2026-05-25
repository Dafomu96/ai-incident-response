"""
rag/ingestion.py — Contextual Retrieval pipeline.

Contextualización desarrollo: Groq Llama 3.3 70B
Contextualización producción: Claude Haiku (más preciso para contexto de chunks)
"""
from __future__ import annotations
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sentence_transformers import SentenceTransformer
from rag.chroma_store import get_collection
from schemas.postmortem import PostmortemDraft

_embedder = SentenceTransformer("all-MiniLM-L6-v2")
_splitter = RecursiveCharacterTextSplitter(chunk_size=512, chunk_overlap=50)


def _get_llm():
    from langchain_groq import ChatGroq
    return ChatGroq(model="llama-3.3-70b-versatile", max_tokens=150)


def _add_context_to_chunk(document: str, chunk: str) -> str:
    from langchain_core.messages import HumanMessage
    prompt = (
        f"<document>{document[:2000]}</document>\n"
        f"<chunk>{chunk}</chunk>\n"
        "In 1-2 sentences, explain what this chunk is about within the document context. "
        "Be specific. Respond only with the context, no preamble."
    )
    response = _get_llm().invoke([HumanMessage(content=prompt)])
    return f"{response.content}\n\n{chunk}"


def ingest_runbook(title: str, content: str, doc_id: str | None = None) -> None:
    collection = get_collection("runbooks")
    chunks = _splitter.split_text(content)
    for i, chunk in enumerate(chunks):
        contextualized = _add_context_to_chunk(content, chunk)
        embedding = _embedder.encode(contextualized).tolist()
        chunk_id = f"{doc_id or title}-chunk-{i}"
        collection.upsert(
            ids=[chunk_id],
            embeddings=[embedding],
            documents=[contextualized],
            metadatas=[{"title": title, "chunk_index": i, "type": "runbook"}],
        )
    print(f"[RAG] Ingestado: '{title}' — {len(chunks)} chunks")


def ingest_postmortem(postmortem: PostmortemDraft) -> None:
    collection = get_collection("runbooks")
    doc_text = postmortem.to_rag_document()
    embedding = _embedder.encode(doc_text).tolist()
    collection.upsert(
        ids=[f"postmortem-{postmortem.alert_id}"],
        embeddings=[embedding],
        documents=[doc_text],
        metadatas=[{
            "type": "postmortem",
            "service": postmortem.service,
            "severity": postmortem.severity,
            "root_cause": postmortem.confirmed_root_cause[:100],
        }],
    )
    print(f"[RAG] Postmortem ingestado: {postmortem.alert_id}")
