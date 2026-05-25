FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -e "." && \
    pip install --no-cache-dir langchain-text-splitters python-multipart

COPY agents/ agents/
COPY graph/ graph/
COPY tools/ tools/
COPY rag/ rag/
COPY schemas/ schemas/
COPY evals/ evals/
COPY api/ api/

EXPOSE 8000

ENV PORT=8000

CMD ["sh", "-c", "uvicorn api.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
