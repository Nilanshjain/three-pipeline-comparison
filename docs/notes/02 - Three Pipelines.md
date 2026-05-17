# 02 - Three Pipelines

> [!summary] The central abstraction
> Three different ways to answer the same question. Same question in, three answers out, plus metrics for each. The whole project is built on this contract.

## What "pipeline" means here

A **pipeline** in this project is a class that takes a query string and returns a `PipelineResult` with the answer + metrics. They all implement the same interface so we can run them in parallel and compare apples-to-apples.

Look at `backend/app/services/pipelines/base.py`:

```python
class Pipeline(ABC):
    name: str = "abstract"

    @abstractmethod
    async def run(self, query: str, **kwargs) -> PipelineResult:
        ...
```

Every pipeline returns the same shape:

```python
@dataclass
class PipelineResult:
    pipeline: str           # "llm_only" | "basic_rag" | "graph_rag"
    answer: str             # the actual response text
    prompt_tokens: int      # tokens sent to the LLM
    completion_tokens: int  # tokens the LLM generated
    latency_ms: float       # end-to-end wall time
    cost_usd: float         # tokens × pricing
    retrieved_chunks: list  # what was retrieved (for inspection)
    model: str              # which LLM was used
    error: str | None       # set if something blew up
```

This shared shape is what makes the dashboard possible — three identical card components rendering whatever each pipeline returned.

## The three pipelines

### Pipeline 1: LLM-Only — see [[04 - Pipeline 1 - LLM Only]]

```
Question → LLM → Answer
```

No retrieval at all. The model answers from its training data ("parametric knowledge"). This is the **baseline**. If the LLM already knew the answer, retrieval is wasted overhead. If the LLM doesn't know, this will hallucinate or refuse.

**Expected behavior**: Cheap (small prompt), fast (one LLM call), often wrong on domain-specific or recent information.

### Pipeline 2: Basic RAG — see [[05 - Pipeline 2 - Basic RAG]]

```
Question → embed → vector search Postgres → top-K chunks → LLM (chunks + question) → Answer
```

The industry-standard RAG pattern. Documents are chunked, embedded into vectors, and stored. At query time, embed the question, find similar chunks, stuff them into the prompt.

**Expected behavior**: Higher accuracy than LLM-Only on domain data. **Much higher token count** because chunks get pasted into the prompt. Slower because of two LLM-related operations (embed + complete).

### Pipeline 3: GraphRAG — see [[06 - Pipeline 3 - GraphRAG]]

```
Question → TigerGraph hybrid retriever
            → (vector search chunks + entity graph traversal + community summaries)
            → focused context → LLM → Answer
```

The proposed improvement. Same vector search as Basic RAG **plus** a knowledge graph of entities and relationships, **plus** community summaries (hierarchical descriptions of entity clusters). The retriever pulls a smaller, more focused context.

**Expected behavior**: Similar or better accuracy than Basic RAG with **fewer tokens** at query time. More expensive at *build time* (LLM calls per chunk for entity extraction), but cheaper per query.

## Why three, not two?

You might ask: "Why include LLM-Only? Of course it'll lose on accuracy questions about the corpus."

Two reasons:
1. **Sanity check.** If LLM-Only gets a question right, your test question is too easy — the LLM already knew the answer, retrieval isn't being tested.
2. **Honest baseline.** It shows token cost of zero retrieval. Sometimes RAG is overkill; LLM-Only is the right answer for general-knowledge questions.

The benchmark report shows token *delta* per pipeline. If LLM-Only is faster and cheaper, that's a legitimate result on that question.

## What "fair comparison" means

For the benchmark to be honest, what must be **the same** across pipelines:

| Thing | Same across pipelines? | Why |
|---|---|---|
| LLM model | ✅ Llama 3.3 70B via Groq | Token counts reflect retrieval strategy, not model choice |
| Question text | ✅ Identical | Obvious |
| System prompt style | ✅ Same brevity | Verbose system prompts inflate token counts |
| Corpus | ✅ Same 432 Wiki articles | All pipelines see the same data |
| Embedding model (Basic RAG vs GraphRAG) | ❌ Different by design | Basic RAG uses local `all-MiniLM-L6-v2`; GraphRAG uses Gemini `text-embedding-001` (required by TigerGraph service) |

The embedding model difference is a real asymmetry we have to acknowledge — see [[14 - Honest Limitations]].

## The flow at request time

When the dashboard hits `POST /api/v1/benchmark/query`:

```
                ┌─→ Pipeline 1 (LLM-Only) ──→ Groq Llama 3.3 70B ───┐
benchmark.py ──┼─→ Pipeline 2 (Basic RAG) ─→ Postgres + Groq ───────┼──→ side-by-side
                └─→ Pipeline 3 (GraphRAG) ─→ TigerGraph + Groq ─────┘    JSON response
                       asyncio.gather() — all three run in parallel
```

See `backend/app/api/benchmark.py:118-144` for the gather call. Failures in one pipeline don't kill the others — `_safe_run()` wraps each call and converts exceptions into an `error` field on the result.

## Related

- [[09 - Benchmark Harness]] — how the parallel execution is implemented
- [[03 - Zero Cost Stack]] — which LLM and embedding services each pipeline uses
- [[10 - Accuracy Evaluation]] — how we grade the three answers

`#architecture` `#pipelines`
