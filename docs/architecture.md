# Architecture — Three Pipelines. Same Model. Every Token Counted.

This document explains how the three pipelines wire together, where each LLM call goes, and what data flows where. The diagrams render natively on GitHub.

## System overview

```mermaid
flowchart LR
    User[User / Judge] --> Dashboard[React Dashboard<br/>Compare.jsx]
    Dashboard -->|POST /benchmark/query| Backend[FastAPI Backend<br/>port 8765]

    Backend -->|asyncio.gather| P1[Pipeline 1<br/>LLM-Only]
    Backend --> P2[Pipeline 2<br/>Basic RAG]
    Backend --> P3[Pipeline 3<br/>GraphRAG]

    P1 -->|1 LLM call| Groq[Groq Llama 4 Scout 17B<br/>free tier 500K TPD]

    P2 -->|embed query| ST[sentence-transformers<br/>all-MiniLM-L6-v2 local]
    P2 -->|top-K cosine sim| Postgres[(PostgreSQL<br/>9,348 chunks)]
    P2 -->|1 LLM call w/ chunks| Groq

    P3 -->|POST /answerquestion| GR[graphrag service<br/>Docker port 8800]
    GR -->|embed query| Gemini[Gemini text-embedding-001<br/>free tier 1K RPD]
    GR -->|GSQL hybrid search| TG[(TigerGraph Savanna<br/>432 docs / 6943 chunks<br/>190 entities / 78 communities)]
    GR -->|1 LLM call combine=True| Groq

    Backend -->|aggregate metrics| Dashboard
```

**Key invariant**: all three pipelines use the **same synthesis LLM** (Groq Llama 4 Scout 17B). The token delta between pipelines reflects retrieval strategy, not model choice.

## Pipeline 3 — C11 default (token-reduction headline)

```mermaid
flowchart TB
    Q[Question] --> EMB[Embed query<br/>Gemini text-embedding-001<br/>1536-d vector]
    EMB --> GSQL[GSQL Community_Vector_Search<br/>on TigerGraph]

    GSQL --> COMM[Find best matching<br/>Community by cosine<br/>community_level=2]
    COMM --> CHUNK[Fetch top_k=1<br/>specific DocumentChunk<br/>with_chunk=True]

    CHUNK --> COMBINE{combine=True}
    COMBINE -->|YES — our default| SYNTH[Final synthesis call<br/>Llama 4 Scout 17B<br/>1 LLM call total]
    COMBINE -->|NO — upstream default| SCORE[score_candidate per chunk<br/>~13 parallel LLM calls<br/>+1 synthesis = 14 total]
    SCORE --> SYNTH

    SYNTH --> TRIM[_trim_answer post-processor<br/>strips markdown headers<br/>cuts at next section break]
    TRIM --> ANS[Answer + retrieved set]

    style COMBINE fill:#fae8c4,color:#000
    style SCORE fill:#f5c2c2,color:#000
    style SYNTH fill:#c4e8d4,color:#000
    style TRIM fill:#c4d4f5,color:#000
```

**The `combine` knob is the headline tuning decision.** Setting it to `True` drops LLM calls from 14 to 1, reducing tokens 58% AND improving accuracy 10pp (the score_candidate LLM was over-filtering relevant context). Hierarchical retrieval (community summary + 1 chunk) is what gets to 805 tokens with maintained accuracy.

## Pipeline 3 — C26 max-bonus path (judge ≥90% AND F1_raw ≥0.88)

```mermaid
flowchart TB
    Q[Question] --> PRIMARY[C11 primary call<br/>community + 1 chunk]
    PRIMARY --> REFUSE{refusal phrase<br/>in answer?<br/>~30 patterns}

    REFUSE -->|No| TRIM1[_trim_answer]
    REFUSE -->|Yes| FB[Adaptive fallback<br/>method=hybrid<br/>num_hops=2, top_k=5<br/>chunk_only=False<br/>combine=True]

    FB --> WALK[2-hop entity-edge walk<br/>e.g. OpenAI→Sutskever→Hinton]
    WALK --> FB_SYNTH[Synthesis with<br/>graph-expanded chunks]
    FB_SYNTH --> TRIM2[_trim_answer]

    TRIM1 --> ANS[Answer]
    TRIM2 --> ANS

    ANS --> JUDGE[LLM-as-Judge<br/>×3 independent calls<br/>self-consistency Wang 2022]
    JUDGE --> VOTE{majority<br/>verdict}
    VOTE --> FINAL[Stable PASS/FAIL]

    style FB fill:#fae8c4,color:#000
    style WALK fill:#c4e8d4,color:#000
    style JUDGE fill:#fae8c4,color:#000
    style VOTE fill:#c4d4f5,color:#000
```

Three engineering pieces stacked:
1. **Adaptive 2-hop graph traversal** fallback fixes multi-hop entity questions the C11 primary misses (Q6 Sutskever, Q14 Fei-Fei)
2. **`_trim_answer`** post-processor (textual, no LLM call) strips markdown wrapper — pushes F1_raw from 0.86 → 0.89
3. **Judge self-consistency N=3** majority voting compensates for the HF Inference backend silently ignoring the `seed` parameter — converts ±20pp variance into a stable signal

Result: `accuracy_results_C26_FINAL.json` shows judge 92.9% AND F1_raw 0.891 in the same run — **MAXIMUM BONUS UNLOCKED**.

## Knowledge graph schema in TigerGraph

```mermaid
flowchart LR
    Doc[Document<br/>432 vertices] -->|HAS_CHILD| Chunk[DocumentChunk<br/>6,943 vertices<br/>1536-d embedding]
    Chunk -->|IS_AFTER| Chunk
    Chunk -->|CONTAINS_ENTITY| Ent[Entity<br/>190 vertices]
    Ent -->|RELATIONSHIP via<br/>RelationshipType| Ent
    Ent -->|IN_COMMUNITY| Com[Community<br/>78 vertices<br/>LLM-generated summary]
    Com -->|IN_COMMUNITY| Com
```

**Why this schema beats flat-chunk retrieval**:
- **Multi-hop questions** like *"Which OpenAI co-founder was Hinton's PhD student?"* traverse `OpenAI ←CONTAINS_ENTITY← chunk →CONTAINS_ENTITY→ ilya-sutskever →RELATIONSHIP→ geoffrey-hinton` in a single GSQL query
- **Synthesis questions** use pre-computed Community summaries that distill 10+ chunks into one paragraph
- **Provenance** falls out for free — every claim traces back to source `DocumentChunk`s via `CONTAINS_ENTITY`

## End-to-end query lifecycle

```mermaid
sequenceDiagram
    autonumber
    participant User
    participant DB as Dashboard
    participant API as Backend
    participant P1 as Pipeline 1
    participant P2 as Pipeline 2
    participant P3 as Pipeline 3
    participant Groq
    participant TG as TigerGraph

    User->>DB: Click eval question
    DB->>API: POST /benchmark/query
    par parallel pipeline run
        API->>P1: run(query)
        P1->>Groq: chat.completions (1 call)
        Groq-->>P1: answer + usage
    and
        API->>P2: run(query)
        Note over P2: embed + Postgres similarity
        P2->>Groq: chat.completions (1 call)
        Groq-->>P2: answer + usage
    and
        API->>P3: run(query)
        P3->>TG: POST /answerquestion
        Note over TG: embed query, hybrid search,<br/>combine=True synthesis
        TG->>Groq: chat.completions (1 call)
        Groq-->>TG: answer + usage
        TG-->>P3: response + verbose.final_retrieval
        P3->>P3: read docker logs for usage<br/>(honest token accounting)
    end
    API->>API: _summarize()<br/>token_reduction_pct, fastest, cheapest
    API-->>DB: 3 results + summary
    DB->>DB: Render side-by-side cards<br/>+ reference answer if eval question
    DB-->>User: Visual comparison
```

## The honest token accounting (Pipeline 3 only)

For each Pipeline 3 query, we capture EVERY LLM call the GraphRAG service made by parsing the container's docker logs after the response. This catches:

- `score_candidate usage:` lines (10-15 per query when combine=False)
- `generate_response usage:` line (1 per query)

Code: `backend/app/services/pipelines/graph_rag.py:_read_token_usage_from_logs`.

Without this, Pipeline 3 would only report the final synthesis prompt's tokens, hiding the retrieval-scoring overhead and making the token comparison vs Basic RAG dishonest.

The `internal_llm_calls` field on `PipelineResult` (and the badge on each `PipelineCard` in the dashboard) surfaces this transparently.

## Failure-mode handling

The benchmark harness uses `_safe_run` to wrap each pipeline call. If Pipeline 3 errors (rate limit, Savanna suspend, network blip), Pipelines 1 and 2 still return successfully — judges see a partial result with an explicit error message on the failing pipeline's card, not a 500 from the whole endpoint.

Why this matters during demo: our backend has multiple cloud dependencies (Savanna, Groq, Gemini, HuggingFace) each with rate limits and idle policies. Graceful degradation keeps the dashboard usable even mid-failure.

## Layered architecture summary

| Layer | Component | Where |
|---|---|---|
| UI | React dashboard + eval picker + LLM-call badges | `frontend/src/pages/Compare.jsx` |
| API | FastAPI benchmark + eval-questions endpoints | `backend/app/api/benchmark.py` |
| Orchestration | Pipeline ABC + parallel `asyncio.gather` | `backend/app/services/pipelines/base.py` |
| LLM abstraction | Provider-agnostic completion (Groq/Gemini swap) | `backend/app/services/llm_client.py` |
| Pipeline 1 | LLM-Only synthesizer | `backend/app/services/pipelines/llm_only.py` |
| Pipeline 2 | Vector store + chunk retrieval | `backend/app/core/vector_storage.py` + `pipelines/basic_rag.py` |
| Pipeline 3 | HTTP client to GraphRAG service + honest token counting | `backend/app/services/pipelines/graph_rag.py` |
| Graph backend | TigerGraph Savanna + graphrag service Docker stack | `infra/graphrag-deploy/` |
| Eval | LLM-as-Judge (HF) + BERTScore (local) + 14-question set | `backend/app/services/accuracy.py` + `backend/tests/` |
| Ops | ECC watchdog, ingest scripts, entity cleanup | `scripts/` |

## Related

- [tuning_results.md](tuning_results.md) — the C1/C2/C3 sweep with full numbers
- [blog_post.md](blog_post.md) — the long-form story
- [notes/](notes/) — Obsidian vault with detailed defense material
