"""
Benchmark API.

POST /api/v1/benchmark/query runs the same query through all three pipelines
in parallel and returns side-by-side metrics. This is what the comparison
dashboard hits.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.services.pipelines import Pipeline, PipelineResult
from app.services.pipelines.basic_rag import BasicRAGPipeline
from app.services.pipelines.graph_rag import GraphRAGPipeline
from app.services.pipelines.llm_only import LLMOnlyPipeline


# Path to the curated 10-question eval set. Surfaced via the API so the
# dashboard can render quick-pick buttons + show the reference answer
# alongside each pipeline's output (judges can verify which pipeline got
# what right).
_EVAL_QUESTIONS_PATH = Path(__file__).resolve().parent.parent.parent / "tests" / "eval_questions.json"


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/benchmark", tags=["benchmark"])


class BenchmarkRequest(BaseModel):
    query: str
    max_chunks: int = 5
    similarity_threshold: float = 0.1
    document_filter: str | None = None
    pipelines: list[str] | None = None  # default: run all three
    # Pipeline 3 / GraphRAG retrieval tuning. None means "use pipeline defaults".
    # Surfaced here so the eval harness can sweep configs without code changes.
    # See backend/app/services/pipelines/graph_rag.py for what each does.
    graphrag_config: dict[str, Any] | None = None


class BenchmarkResponse(BaseModel):
    query: str
    pipelines: list[dict[str, Any]]
    summary: dict[str, Any]


def _build_pipelines(
    db: Session,
    selected: list[str] | None,
    max_chunks: int,
    similarity_threshold: float,
) -> list[Pipeline]:
    all_pipelines: dict[str, Pipeline] = {
        "llm_only": LLMOnlyPipeline(),
        "basic_rag": BasicRAGPipeline(
            db=db,
            max_chunks=max_chunks,
            similarity_threshold=similarity_threshold,
        ),
        "graph_rag": GraphRAGPipeline(),
    }
    if selected is None:
        return list(all_pipelines.values())
    unknown = set(selected) - all_pipelines.keys()
    if unknown:
        raise HTTPException(status_code=400, detail=f"Unknown pipelines: {sorted(unknown)}")
    return [all_pipelines[name] for name in selected]


async def _safe_run(pipeline: Pipeline, query: str, **kwargs: Any) -> PipelineResult:
    """Wrap pipeline.run so one failure doesn't kill the whole comparison."""
    try:
        return await pipeline.run(query, **kwargs)
    except NotImplementedError as e:
        logger.info("Pipeline %s not yet implemented: %s", pipeline.name, e)
        return PipelineResult(
            pipeline=pipeline.name,
            answer="",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0.0,
            cost_usd=0.0,
            error=f"not_implemented: {e}",
        )
    except Exception as e:
        logger.exception("Pipeline %s failed", pipeline.name)
        return PipelineResult(
            pipeline=pipeline.name,
            answer="",
            prompt_tokens=0,
            completion_tokens=0,
            latency_ms=0.0,
            cost_usd=0.0,
            error=str(e),
        )


def _summarize(results: list[PipelineResult]) -> dict[str, Any]:
    """Headline metrics: token reduction vs Basic RAG, fastest pipeline, cheapest."""
    successful = [r for r in results if not r.error and r.total_tokens > 0]
    summary: dict[str, Any] = {"successful_pipelines": len(successful)}

    basic = next((r for r in successful if r.pipeline == "basic_rag"), None)
    if basic:
        summary["basic_rag_total_tokens"] = basic.total_tokens
        for r in successful:
            if r.pipeline == "basic_rag":
                continue
            delta = basic.total_tokens - r.total_tokens
            pct = (delta / basic.total_tokens * 100) if basic.total_tokens else 0.0
            summary[f"{r.pipeline}_token_reduction_vs_basic_pct"] = round(pct, 2)

    if successful:
        summary["fastest_pipeline"] = min(successful, key=lambda r: r.latency_ms).pipeline
        summary["cheapest_pipeline"] = min(successful, key=lambda r: r.cost_usd).pipeline

    return summary


@router.post("/query", response_model=BenchmarkResponse)
async def benchmark_query(
    request: BenchmarkRequest,
    db: Session = Depends(get_db),
) -> BenchmarkResponse:
    pipelines = _build_pipelines(
        db,
        request.pipelines,
        request.max_chunks,
        request.similarity_threshold,
    )

    kwargs = {
        "max_chunks": request.max_chunks,
        "similarity_threshold": request.similarity_threshold,
        "document_filter": request.document_filter,
    }
    # Merge graphrag-specific kwargs (combine, chunk_only, top_k, num_hops, etc.).
    # Pipelines ignore kwargs they don't recognize, so it's safe to forward to all.
    if request.graphrag_config:
        kwargs.update(request.graphrag_config)

    results = await asyncio.gather(
        *(_safe_run(p, request.query, **kwargs) for p in pipelines)
    )

    return BenchmarkResponse(
        query=request.query,
        pipelines=[r.to_dict() for r in results],
        summary=_summarize(list(results)),
    )


@router.get("/eval-questions")
async def get_eval_questions() -> list[dict[str, Any]]:
    """Return the curated benchmark eval set so the dashboard can render
    quick-pick buttons + display the reference answer alongside the
    pipelines' outputs. See backend/tests/eval_questions.json for the source."""
    if not _EVAL_QUESTIONS_PATH.exists():
        raise HTTPException(status_code=500, detail=f"eval_questions.json not found at {_EVAL_QUESTIONS_PATH}")
    return json.loads(_EVAL_QUESTIONS_PATH.read_text(encoding="utf-8"))


@router.get("/health")
async def benchmark_health() -> dict[str, Any]:
    """Quick check that pipelines can be instantiated."""
    status: dict[str, Any] = {}
    for name, factory in [
        ("llm_only", lambda: LLMOnlyPipeline()),
        ("graph_rag", lambda: GraphRAGPipeline()),
    ]:
        try:
            factory()
            status[name] = "ready"
        except Exception as e:
            status[name] = f"error: {e}"
    status["basic_rag"] = "requires db session (instantiated per-request)"
    return status
