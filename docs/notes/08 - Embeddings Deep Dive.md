# 08 - Embeddings Deep Dive

> [!summary] One sentence
> Embeddings turn text into vectors of numbers such that "semantically similar" texts are close together in that vector space.

If you're newer to ML, this note covers the intuition. If you already know embeddings, skim to the project-specific details.

## What is an embedding?

A function `f(text) -> vector` where the vector is a fixed-length list of floats. Properties:

- **Determinism**: same input → same output, every time
- **Semantic locality**: similar inputs → close vectors (close in cosine or Euclidean distance)
- **Dimensionality**: typical sizes are 384, 768, 1024, 1536, or 3072 floats

You can think of each dimension as encoding *some property* of the text, learned during training. You don't know what each dimension means (that's emergent), but you trust that the cluster of "vectors close to my query vector" share meaning with my query.

### Concrete example

For the sentence transformer `all-MiniLM-L6-v2` (384-d), here's what happens:

```
embed("the cat sat on the mat")
  -> [0.024, -0.107, 0.453, ..., 0.012]    (384 numbers)

embed("a feline rested on a rug")
  -> [0.029, -0.103, 0.448, ..., 0.011]    (very similar 384 numbers)

cosine_similarity(above two) ≈ 0.92

embed("quantum chromodynamics")
  -> [0.612, 0.011, -0.245, ..., -0.078]   (very different 384 numbers)

cosine_similarity(cat sentence vs QCD) ≈ 0.08
```

## What does "cosine similarity" mean?

For two vectors `a` and `b`, cosine sim is `(a · b) / (|a| × |b|)`. It measures the **angle** between them, ignoring magnitude.

- `1.0` = same direction → semantically identical-ish
- `0.0` = orthogonal → unrelated
- `-1.0` = opposite

In RAG we usually only care about `> 0` similarities. Typical "highly relevant chunk" scores:
- `0.85+` = nearly exact match
- `0.6 - 0.85` = strong relevance
- `0.4 - 0.6` = topical
- `< 0.4` = noise

Our `similarity_threshold = 0.5` (Pipeline 3) discards weak matches.

## Two embedding models in our project

### Pipeline 2 (Basic RAG): `sentence-transformers/all-MiniLM-L6-v2`

- **384 dimensions**
- Runs locally on CPU (no API calls)
- Trained on `1B+ sentence pairs`
- Fast: ~10ms per text on a laptop CPU
- Good enough for English text; weaker on code, technical jargon

We use this because it's **free, unlimited, fast** — no rate limits, no API key, no per-call cost.

### Pipeline 3 (GraphRAG): Google Gemini `text-embedding-001`

- **1536 dimensions** (configurable 128-3072 in newer versions)
- API call to Google's GenAI service
- Trained on Google's large multilingual corpus
- Slower: ~150ms per text (network round-trip)
- Free tier: **1,000 requests per day**

We use this because the TigerGraph GraphRAG service requires one of its supported embedding providers (`openai`, `azure`, `vertexai`, `genai`, `bedrock`, `ollama`). Gemini is the only zero-cost option in that list.

## Why two different models is an asymmetry we should acknowledge

In [[02 - Three Pipelines]] we promise "same model across pipelines for fair comparison." But Pipeline 2 uses `all-MiniLM-L6-v2` and Pipeline 3 uses `text-embedding-001`. That's a divergence.

**The honest take**:
- The retrieval *quality* might differ slightly for reasons unrelated to graph-vs-vector. A larger 1536-d model captures more nuance than a 384-d one.
- We accepted this because:
  - Pipeline 2 with sentence-transformers is free & instant
  - Pipeline 3 *can't* easily use sentence-transformers (the upstream service has no plugin for it without code changes)
  - The accuracy difference is small enough that the headline (graph traversal advantage) dominates

We document this in [[14 - Honest Limitations]].

## How embeddings are stored

### Pipeline 2: PostgreSQL JSON

Schema: `vector_documents(id, filename, chunk_text, chunk_index, embedding)`. The `embedding` column is a `JSON` array of 384 floats. Cosine sim is computed in Python (`backend/app/core/vector_storage.py`).

Tradeoff: simple, no extensions needed; slow for >100K chunks. With 9,348 chunks we run cosine in ~50ms — fast enough.

A "real" solution would use the `pgvector` extension which adds:
- A `vector(384)` column type
- Native cosine / Euclidean / dot-product operators
- IVFFlat / HNSW indexes for sublinear search

We didn't bother because the dataset is small.

### Pipeline 3: TigerGraph native vector index

TigerGraph 4.2+ has built-in vector storage. The `DocumentChunk.embedding` attribute is a 1536-d vector with an associated index. The GSQL query `GraphRAG_Hybrid_Vector_Search.gsql` uses `gds.vector.cosine_distance()` for similarity.

This is what required the **GDS library install** during setup — see [[11 - Failures and Learnings]] for the apiToken scope drama that caused.

## Why dimensions matter

More dimensions = more capacity to encode subtle semantic distinctions, but also:
- More storage (1536 × 4 bytes = 6 KB per chunk vs 384 × 4 = 1.5 KB)
- Slower similarity computation
- More API/compute cost

For RAG over English text, 384-d is usually enough. 1536-d helps mostly when:
- The corpus has technical jargon, multilingual content, or code
- You're at very large scale (millions+ of chunks) and need fine-grained ranking
- The downstream task is more than just retrieval (e.g., classification, clustering)

## Common confusions

### "Aren't embeddings just hashed text?"
No. Hashes are designed so similar inputs give totally different outputs (avalanche effect). Embeddings are the opposite — similar inputs give similar outputs.

### "Why not just use the LLM directly to compare?"
You can — and `score_candidate` does. But:
- Embeddings are 100-1000× faster than LLM calls
- For 9,000 chunks × every query, you can't afford 9,000 LLM calls each time
- Embeddings let you pre-compute, store, and do approximate-nearest-neighbor search

The "honest token accounting" issue in Pipeline 3 ([[06 - Pipeline 3 - GraphRAG]]) was exactly this — the LLM `score_candidate` step is expensive precisely because it skips embeddings.

### "Cosine vs Euclidean — which is right?"
For normalized embeddings (length 1), they're equivalent up to a transformation. Most embedding models output normalized vectors. We use cosine because it's the convention for RAG.

## Related

- [[05 - Pipeline 2 - Basic RAG]] — uses MiniLM
- [[06 - Pipeline 3 - GraphRAG]] — uses Gemini
- [[11 - Failures and Learnings]] — the Gemini embed quota wall, the `text-embedding-004` deprecation
- [[14 - Honest Limitations]] — the embedding-model asymmetry

`#embeddings` `#vectors` `#ml-fundamentals`
