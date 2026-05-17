# 06 - Pipeline 3 - GraphRAG

> [!summary] One sentence
> Same vector search as Basic RAG plus a knowledge graph of entities, relationships, and community summaries — the retriever traverses the graph to assemble a focused context.

This is the most complex pipeline. It's also the headline of the project.

## What it does

```
Question
   │
   ▼
[GraphRAG service @ localhost:8800]
   │
   ├── 1. Embed question (Gemini text-embedding-001, 1536-d)
   ├── 2. Hybrid Search GSQL query against TigerGraph:
   │     - Find top-K chunks by vector cosine
   │     - From each chunk, traverse num_hops edges (chunk → entity → relationship → entity → chunk)
   │     - Collect "selected_set" of (chunks + entities) connected to the question
   ├── 3. If combine=True (our default): concat all retrieved into one context
   │     If combine=False: score each candidate with an LLM call ("score_candidate"), keep top-k
   ├── 4. Final LLM synthesis on (system_prompt + context + question)
   │
   ▼
Answer + retrieved set
```

Code: `backend/app/services/pipelines/graph_rag.py`. The hard work happens inside the `tigergraph/graphrag` Docker container which talks to TigerGraph Savanna.

## Architecture in one diagram

```
                              ┌────────────────────────┐
                              │  TigerGraph Savanna    │
                              │  (cloud-hosted DB)     │
                              │                        │
                              │  Documents             │
                              │  └─ DocumentChunks     │
                              │     ├─ embedding (vec) │
                              │     └─ CONTAINS_ENTITY │
                              │           ↓            │
                              │        Entities ◄──────┼─── 190 of them
                              │           ↓            │
                              │     RELATIONSHIPS      │
                              │           ↓            │
                              │     Communities ◄──────┼─── 78 of them
                              └────────────▲───────────┘
                                           │ apiToken
                              ┌────────────┴───────────┐
                              │  graphrag service      │
                              │  (Docker, port 8800)   │
                              │                        │
                              │  HybridRetriever       │
                              │  + LLM (Llama 4 Scout) │
                              │  + Gemini embeddings   │
                              └────────────▲───────────┘
                                           │ HTTP
                              ┌────────────┴───────────┐
                              │  DevRAG backend        │
                              │  /api/v1/benchmark     │
                              └────────────────────────┘
```

The DevRAG backend just **proxies** to the graphrag service. All the GraphRAG smarts live inside the container + TigerGraph.

## What's a knowledge graph?

A graph where:
- **Vertices (nodes)** are entities — people, places, concepts (`demis-hassabis`, `deepmind`, `transformer-architecture`)
- **Edges** are relationships between them (`founded(demis-hassabis, deepmind)`, `developed(google-brain, transformer)`)

Why this beats vector search alone: vector search finds chunks that *mention similar words*. A graph traversal can answer questions like "which DeepMind researchers also worked at OpenAI?" — even if no single chunk literally contains both facts.

See [[07 - Knowledge Graph Schema]] for what TigerGraph actually stores.

## What's a community?

After entities are extracted, the system runs **Louvain community detection** (a graph clustering algorithm) on the entity graph. Each community = a cluster of densely-interconnected entities. The system then generates an LLM summary for each community ("This community is about DeepMind founders and their AlphaFold work").

Communities give the LLM a *bird's-eye view* of a topic. Instead of stuffing 10 chunks into the prompt, you can stuff 1 community summary that distills the same information.

We have **78 communities** in our graph.

## How retrieval works (the HybridRetriever)

Source: `infra/graphrag-upstream/graphrag/app/supportai/retrievers/HybridRetriever.py`.

1. **Vector search anchor**: embed the question, find top_k (default 5) DocumentChunks with highest cosine similarity to the query vector.
2. **Graph traversal**: from each anchor chunk, walk `num_hops` (default 2) edges through the entity graph. Collect every vertex reached.
3. **Filter**: keep only vertices that appear in ≥ `num_seen_min` paths (default 1) — prunes isolated noise.
4. **Score** (if `combine=False`): for each retrieved candidate, ask the LLM "how relevant is this to the question, score 0-100?". Keep top-K by score. **This is the 13 extra LLM calls** the upstream default makes.
5. **Combine** (if `combine=True` — our default after tuning): skip scoring, dump all retrieved into one prompt.
6. **Synthesize**: final LLM call answers the question using the assembled context.

See [[11 - Failures and Learnings]] for why we chose `combine=True` and [[docs/tuning_results.md]] for the supporting data.

## Configuration knobs

In `backend/app/services/pipelines/graph_rag.py`:

| Param | Default | Effect |
|---|---|---|
| `top_k` | 5 | How many chunks to pull as initial anchors |
| `num_hops` | 2 | Graph traversal depth from anchors |
| `num_seen_min` | 1 | Min paths a vertex must appear in (filter) |
| `similarity_threshold` | 0.50 | Min cosine similarity for an anchor (upstream default 0.90 was too strict for our 1536-d Gemini embeddings) |
| `combine` | **True** | Skip LLM-based re-ranking. 14 LLM calls → 1. Counter-intuitively *raised* our accuracy 80% → 90% |
| `chunk_only` | False | If true, retrieve only chunks, no entity vertices |
| `expand` | False | If true, generate 10 question variations and retrieve for each — accuracy↑, tokens↑↑ |

## Metrics this pipeline produces

For "Who founded DeepMind?" (our C2 default config):

| Metric | Value | Interpretation |
|---|---|---|
| `prompt_tokens` | ~4,700 | All retrieved chunks + entities concatenated |
| `completion_tokens` | ~70 | The final answer |
| `total_tokens` | ~4,800 | Honest count via `_read_token_usage_from_logs` |
| `internal_llm_calls` | **1** | Single synthesis call (combine=True) |
| `latency_ms` | ~7,000 | Graph traversal + Gemini embed + Groq synthesis |
| `retrieved_chunks` | varies | Mix of DocumentChunks and Entity vertices |

Compare to Basic RAG (~1,270 tokens, 1 LLM call) — we use **~3.7× more tokens** but get **+30pp accuracy**. The tradeoff.

## Why this pipeline took most of the engineering time

This pipeline hit **every wall** in [[11 - Failures and Learnings]]:

1. Savanna workspace auto-suspended → forced manual restart
2. apiToken was graph-scoped → GDS install failed
3. Embedding model `text-embedding-004` was deprecated
4. ECC autostart had an async/sync bug — needed manual triggering
5. Local file loading didn't work with Savanna (cloud DB can't see Docker filesystem)
6. Upstream `llama_70b/` prompts dir was incomplete → silent extraction failures
7. Llama 3.1 8B produced garbage entities for structured extraction
8. Groq daily TPD limit hit during bulk re-extraction
9. Gemini embed quota hit during bulk re-embedding
10. The upstream service's response shape changed (`response`/`retrieved`/`verbose` instead of `natural_language_response`/`query_sources`)
11. Default `similarity_threshold=0.90` was too strict — retriever returned 0 chunks

Pipelines 1 and 2 each took ~1 hour. Pipeline 3 took the whole rest of the project. That's the GraphRAG reality.

## The defensible claim

> *"Pipeline 3 achieved 90% LLM-as-Judge pass rate at ~4,800 tokens per query — vs Basic RAG's 60% at ~1,270 tokens. The graph traversal + community summaries trade ~3.7× tokens for ~30pp accuracy on multi-hop and synthesis questions."*

Be careful not to overclaim:
- This is **on AI/ML Wikipedia**, a densely cross-linked corpus where graphs help most
- We did **not** beat Basic RAG on raw tokens
- Pipeline 1 (LLM-Only) also got 90% because the questions are well-known public knowledge — the test wasn't a true *information-retrieval* test for general questions

## Related

- [[07 - Knowledge Graph Schema]] — what TigerGraph actually stores
- [[08 - Embeddings Deep Dive]] — how Gemini text-embedding-001 differs from sentence-transformers
- [[11 - Failures and Learnings]] — the 11+ walls we hit on this pipeline
- [[13 - Defending The Project]] — anticipated judge questions about GraphRAG

`#pipeline-3` `#graphrag` `#tigergraph`
