# 09 - Benchmark Harness

> [!summary] One sentence
> The `/api/v1/benchmark/query` endpoint runs all three pipelines in parallel against the same question, captures metrics per pipeline, and returns a side-by-side report.

This is what the dashboard hits. It's the single source of truth for "how do the pipelines compare?".

## File location

`backend/app/api/benchmark.py` — ~165 lines, mostly boilerplate.

## The contract

### Request

```json
POST /api/v1/benchmark/query
{
  "query": "Who founded DeepMind?",
  "max_chunks": 5,              // optional, Pipeline 2 top_k
  "similarity_threshold": 0.1,  // optional, Pipeline 2 floor
  "document_filter": null,      // optional, Pipeline 2 filename filter
  "pipelines": null,            // optional, subset like ["graph_rag"]
  "graphrag_config": {          // optional, Pipeline 3 retrieval tuning
    "combine": true,
    "top_k": 3,
    "num_hops": 1
  }
}
```

### Response

```json
{
  "query": "Who founded DeepMind?",
  "pipelines": [
    {
      "pipeline": "llm_only",
      "answer": "DeepMind was founded by...",
      "prompt_tokens": 14,
      "completion_tokens": 60,
      "total_tokens": 74,
      "latency_ms": 530,
      "cost_usd": 0.0,
      "retrieved_chunks": [],
      "model": "meta-llama/llama-4-scout-17b-16e-instruct",
      "internal_llm_calls": 1
    },
    { /* basic_rag */ },
    { /* graph_rag */ }
  ],
  "summary": {
    "successful_pipelines": 3,
    "basic_rag_total_tokens": 1640,
    "llm_only_token_reduction_vs_basic_pct": 95.5,
    "graph_rag_token_reduction_vs_basic_pct": -204.5,
    "fastest_pipeline": "llm_only",
    "cheapest_pipeline": "llm_only"
  }
}
```

## The parallel-execution trick

```python
results = await asyncio.gather(
    *(_safe_run(p, request.query, **kwargs) for p in pipelines)
)
```

All three pipelines run simultaneously. End-to-end latency is the **max** of the three, not the sum. For our typical request:
- Pipeline 1: ~700ms
- Pipeline 2: ~12s
- Pipeline 3: ~7s

Total wall time ≈ 12s (Pipeline 2 dominates because vector search + LLM round-trip).

## Why `_safe_run`?

```python
async def _safe_run(pipeline, query, **kwargs):
    try:
        return await pipeline.run(query, **kwargs)
    except Exception as e:
        return PipelineResult(pipeline=pipeline.name, ..., error=str(e))
```

If one pipeline fails (rate limit, network error, etc.), the other two still return. The dashboard shows the failed pipeline's card with an error message instead of crashing.

Critical for the hackathon: judges will hammer the dashboard, and our backend has dependencies (Savanna, Groq, Gemini) that can fail. Graceful degradation matters.

## The `summary` block

`_summarize()` computes headline metrics across the three results:

- **`successful_pipelines`**: count of pipelines that didn't error
- **`basic_rag_total_tokens`**: anchor for comparison
- **`{name}_token_reduction_vs_basic_pct`**: per-pipeline `(basic - this) / basic × 100`
  - Positive = this pipeline used FEWER tokens (good)
  - Negative = this pipeline used MORE tokens (bad)
- **`fastest_pipeline`**: minimum latency
- **`cheapest_pipeline`**: minimum cost (all $0 on free tier so this is informational)

## What the summary metrics actually mean

Be precise when interpreting:

| Phrase | Means |
|---|---|
| `graph_rag_token_reduction_vs_basic_pct: -204` | GraphRAG used 3.04× as many tokens as Basic RAG |
| `graph_rag_token_reduction_vs_basic_pct: 30` | GraphRAG used 70% of Basic RAG's tokens |

The math: a 25% reduction means tokens dropped from 1000 to 750. A 50% reduction means dropped to 500. A negative "reduction" means an increase.

## Eval-questions endpoint

`GET /api/v1/benchmark/eval-questions` — returns the 10 curated questions from `backend/tests/eval_questions.json`. The dashboard fetches these on page load to render the quick-pick panel.

This is the [[13 - Defending The Project]] "click any question" feature judges will play with.

## How the eval script uses the harness

`backend/tests/accuracy_eval.py` calls `/benchmark/query` once per eval question, captures the results, then runs each pipeline's answer through:
1. **LLM-as-Judge** (HuggingFace Llama-3.1-8B-Instruct) — PASS/FAIL grading
2. **BERTScore** (optional, slow) — semantic similarity to reference

Then aggregates: pass rate, avg tokens, avg latency per pipeline.

Use the `--graphrag-config` flag to sweep configs without code changes:

```
python tests/accuracy_eval.py --skip-bertscore \
    --api http://localhost:8765/api/v1/benchmark/query \
    --graphrag-config '{"combine": true, "top_k": 3}'
```

## Common runtime issues

- **Port conflict**: the user has another project on 8000/8001. Backend now defaults to **8765**.
- **`/eval-questions` 404**: ensure backend was restarted after the endpoint was added.
- **Rate limits**: Groq's 30 RPM is generous but ECC can starve the harness if it's running. Stop ECC before eval runs.
- **CORS**: `main.py` allows `http://localhost:3000` (the React dev server origin). If frontend runs elsewhere, add the origin.

## Related

- [[02 - Three Pipelines]] — the Pipeline interface this harness depends on
- [[10 - Accuracy Evaluation]] — what happens after the harness returns
- [[03 - Zero Cost Stack]] — what each pipeline's `complete()` actually calls

`#api` `#benchmark` `#harness`
