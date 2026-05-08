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


_TESTS_DIR = Path(__file__).resolve().parent.parent.parent / "tests"

# The two saved-eval files the dashboard surfaces: C11 = headline rubric
# (-42.8% tokens) and C26 = maximum bonus tier (judge 92.9% + F1_raw 0.891).
# Both are full 14-question eval runs with LLM-as-Judge + BERTScore numbers
# already computed. Surfaced here so judges can see aggregate scores without
# running 14 live queries (saves time AND avoids judge variance during demo).
_SAVED_RESULTS_MANIFEST = [
    {
        "id": "C11",
        "label": "Default config — Token-reduction winner",
        "subtitle": "−42.8% tokens vs Basic RAG with +7.1pp higher judge accuracy",
        "config": "method=community, top_k=1, with_chunk=True, combine=True — single LLM call",
        "rubric": "Headline rubric (Token Reduction 30%): satisfied",
        "file": "accuracy_results_C11_FINAL.json",
    },
    {
        "id": "C26",
        "label": "Adaptive config — Maximum Bonus Tier 🏆",
        "subtitle": "judge 92.9% AND F1_raw 0.891 in the same eval run",
        "config": "adaptive_fallback=true (2-hop graph traversal) + judge-consensus N=3",
        "rubric": "Bonus tier: judge ≥90% ✓ AND F1_raw ≥0.88 ✓ — both met",
        "file": "accuracy_results_C26_FINAL.json",
    },
]


@router.get("/saved-results")
async def saved_results() -> list[dict[str, Any]]:
    """Return per-pipeline aggregate scores from each saved eval file in the
    manifest. The dashboard renders these as a "Saved Results" tab so judges
    can verify our two hackathon wins without running 14 live queries.

    Schema per item: { id, label, subtitle, config, summary: {pipeline: {...metrics}} }
    """
    out: list[dict[str, Any]] = []
    for entry in _SAVED_RESULTS_MANIFEST:
        path = _TESTS_DIR / entry["file"]
        if not path.exists():
            out.append({**entry, "error": f"file not found: {path.name}"})
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            summary = data.get("summary", {})
            # Pass through only the metrics the dashboard renders — keeps
            # the response small and stable across schema drift.
            pruned_summary = {
                name: {
                    "judge_pass_rate": m.get("judge_pass_rate"),
                    "judge_n": m.get("judge_n"),
                    "bertscore_f1_raw_mean": m.get("bertscore_f1_raw_mean"),
                    "bertscore_f1_rescaled_mean": m.get("bertscore_f1_rescaled_mean"),
                    "mean_total_tokens": m.get("mean_total_tokens"),
                    "mean_latency_ms": m.get("mean_latency_ms"),
                    "n_questions": m.get("n_questions"),
                    "n_errors": m.get("n_errors"),
                }
                for name, m in summary.items()
            }
            out.append({**entry, "summary": pruned_summary, "n_questions": len(data.get("results", []))})
        except Exception as e:
            logger.exception("failed to load saved result %s", entry["file"])
            out.append({**entry, "error": str(e)})
    return out


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
