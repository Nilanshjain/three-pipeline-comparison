"""
Pipeline 2: Basic RAG.

Cosine-similarity over chunk embeddings (Postgres) + LLM synthesis.
Uses the same LLM as Pipelines 1 and 3 so token deltas across pipelines
reflect retrieval strategy, not model choice.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.vector_storage import PostgreSQLVectorStorage
from app.services.embeddings import get_embedding_service
from app.services.llm_client import complete, cost_usd
from app.services.pipelines.base import Pipeline, PipelineResult, RetrievedChunk


# Deliberately concise. The benchmark needs comparable prompts across
# pipelines — a verbose system prompt inflates Basic RAG's token count
# unfairly. Tuning lands in Task #13.
SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using the "
    "provided context. If the context is insufficient, say so briefly."
)


class BasicRAGPipeline(Pipeline):
    name = "basic_rag"

    def __init__(
        self,
        db: Session,
        max_chunks: int = 5,
        similarity_threshold: float = 0.1,
    ) -> None:
        self._db = db
        self._max_chunks = max_chunks
        self._similarity_threshold = similarity_threshold

    async def run(self, query: str, **kwargs: Any) -> PipelineResult:
        max_chunks = kwargs.get("max_chunks", self._max_chunks)
        similarity_threshold = kwargs.get("similarity_threshold", self._similarity_threshold)
        document_filter = kwargs.get("document_filter")

        start = time.perf_counter()

        retrieved = await asyncio.to_thread(
            self._retrieve, query, max_chunks, similarity_threshold, document_filter
        )

        prompt = self._build_prompt(query, retrieved)
        result = await complete(prompt)

        latency_ms = (time.perf_counter() - start) * 1000

        return PipelineResult(
            pipeline=self.name,
            answer=result.text,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd(
                settings.llm_provider, result.model,
                result.prompt_tokens, result.completion_tokens,
            ),
            retrieved_chunks=retrieved,
            model=result.model,
        )

    def _retrieve(
        self,
        query: str,
        max_chunks: int,
        similarity_threshold: float,
        document_filter: str | None,
    ) -> list[RetrievedChunk]:
        embedding_service = get_embedding_service()
        query_embedding = embedding_service.generate_embedding(query)

        store = PostgreSQLVectorStorage(self._db)
        results = store.similarity_search(
            query_embedding=query_embedding,
            limit=max_chunks,
            similarity_threshold=similarity_threshold,
            filename_filter=document_filter,
        )

        return [
            RetrievedChunk(
                text=doc.chunk_text,
                source=doc.filename,
                score=float(score),
                metadata={"chunk_index": doc.chunk_index, "document_id": doc.id},
            )
            for doc, score in results
        ]

    @staticmethod
    def _build_prompt(query: str, chunks: list[RetrievedChunk]) -> str:
        if chunks:
            context_block = "\n\n".join(
                f"[{c.source} #{c.metadata.get('chunk_index', '?')}]\n{c.text}"
                for c in chunks
            )
            context_section = f"Context:\n{context_block}\n\n"
        else:
            context_section = ""

        return f"{SYSTEM_PROMPT}\n\n{context_section}Question: {query}\n\nAnswer:"
