"""
Pipeline 1: LLM-Only.

No retrieval. The model answers from its parametric knowledge alone.
Worst-case baseline for the comparison.
"""

from __future__ import annotations

import time
from typing import Any

from app.core.config import settings
from app.services.llm_client import complete, cost_usd
from app.services.pipelines.base import Pipeline, PipelineResult


class LLMOnlyPipeline(Pipeline):
    name = "llm_only"

    async def run(self, query: str, **_: Any) -> PipelineResult:
        start = time.perf_counter()
        result = await complete(query)
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
            retrieved_chunks=[],
            model=result.model,
        )
