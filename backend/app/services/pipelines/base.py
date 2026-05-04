"""
Common pipeline interface.

All three RAG variants (LLM-Only, Basic RAG, GraphRAG) implement Pipeline.run()
and return a PipelineResult with the metrics the hackathon judges on:
tokens, latency, cost, plus the answer and any retrieved context.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


# Per-provider pricing lives in app.services.llm_client (so swapping LLM
# provider only touches one place). Importing here would create a cycle,
# so callers import cost_usd from llm_client directly.


@dataclass
class RetrievedChunk:
    text: str
    source: str
    score: float | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PipelineResult:
    pipeline: str
    answer: str
    prompt_tokens: int
    completion_tokens: int
    latency_ms: float
    cost_usd: float
    retrieved_chunks: list[RetrievedChunk] = field(default_factory=list)
    model: str = ""
    error: str | None = None
    # How many LLM calls this query incurred end-to-end.
    # Pipelines 1 and 2 always = 1 (one synthesis call).
    # Pipeline 3 typically = 10-20 (one per candidate score + one for synthesis).
    # We report this so the token comparison is transparent: GraphRAG's tokens
    # include the cost of LLM-based retrieval scoring, not just synthesis.
    internal_llm_calls: int = 1

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["total_tokens"] = self.total_tokens
        return d


class Pipeline(ABC):
    """Common contract every pipeline implements."""

    name: str = "abstract"

    @abstractmethod
    async def run(self, query: str, **kwargs: Any) -> PipelineResult:
        """Answer the query and return metrics."""
