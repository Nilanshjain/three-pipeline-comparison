# 05 - Pipeline 2 - Basic RAG

> [!summary] One sentence
> Embed the question, vector-search Postgres for similar chunks, stuff them into the prompt, call the LLM.

This is the **industry-standard RAG pattern** as of 2024-2026. Most production "chat with your docs" apps work this way.

## The flow

```
                                                    ┌──→ Postgres ──┐
Question ──→ embedding model ──→ query vector ──────┤  (cosine sim)  │
                                                    └──→ top-K chunks┘
                                                                ↓
                                       Question + chunks → LLM → Answer
```

Five steps:
1. **Embed the question** into a 384-dimensional vector using sentence-transformers (local, free)
2. **Search Postgres** — compute cosine similarity between the query vector and every stored chunk vector, take top-K (default 5)
3. **Build the prompt** — `SYSTEM_PROMPT + retrieved chunks + question`
4. **Call the LLM** (Groq Llama 3.3 70B) with that prompt
5. **Return the answer** plus the chunks for inspection

Code: `backend/app/services/pipelines/basic_rag.py`.

## Prerequisites — what's done ahead of time

At **build time** (not at query time), we ran `scripts/ingest_basicrag.py`:

1. Read all 432 articles from `data/raw_articles/`
2. For each article:
   - **Chunk** it into ~1000-character pieces with 200-character overlap. Smart chunking respects paragraph boundaries (`backend/app/services/chunking.py`)
   - For each chunk, generate a 384-d embedding (`backend/app/services/embeddings.py`)
   - INSERT into Postgres table `vector_documents` with columns: filename, chunk_text, chunk_index, embedding (as JSON array)

Resulting state: **9,348 chunks** across **448 documents** (some legacy uploads alongside the 432 Wikipedia articles).

## What's a chunk and why chunk at all?

Articles are too big to send to an LLM whole (and most isn't relevant to any given question). Chunking = split the document into pieces, embed each piece, retrieve only the relevant pieces.

Why ~1000 characters? Tradeoff:
- **Smaller chunks**: more precise retrieval (only relevant text), but lose context. A sentence taken out of context can lose meaning.
- **Larger chunks**: more context per chunk, but more wasted tokens — you pull in a whole page when only one paragraph is relevant.

1000 characters with 200-char overlap is a common sweet spot. The overlap means a sentence at the boundary appears in two consecutive chunks, so retrieval doesn't fail if the relevant sentence happens to land on a chunk edge.

## What's an embedding?

A **vector representation of text** in some high-dimensional space, where semantically similar texts have similar vectors. For `all-MiniLM-L6-v2`:
- 384 dimensions
- Trained so that `"The cat sat on the mat"` and `"A feline rested on a rug"` produce nearly-identical vectors (high cosine similarity).
- Trained so that `"Demis Hassabis"` and `"Quantum chromodynamics"` produce vectors far apart.

Cosine similarity ranges -1 to 1:
- `1.0` = identical direction
- `0.0` = orthogonal (unrelated)
- `-1.0` = opposite

In practice, "highly relevant" chunks score ~0.5–0.85. See [[08 - Embeddings Deep Dive]] for math + intuition.

## The prompt structure

After retrieval, Pipeline 2 builds a prompt that looks like this:

```
You are a helpful assistant. Answer the user's question using the provided context.
If the context is insufficient, say so briefly.

Context:
[demis_hassabis.txt #4]
Demis Hassabis (born 27 July 1976) is a British artificial intelligence
researcher, neuroscientist, and entrepreneur, who is the co-founder and
CEO of Google DeepMind...

[deepmind.txt #0]
DeepMind Technologies Limited is a British artificial intelligence
research laboratory founded in London in 2010, that became a wholly
owned subsidiary of Alphabet Inc, Google's parent company, in 2014...

[geoffrey_hinton.txt #2]
... [3 more chunks] ...

Question: Who founded DeepMind, and in what year and city?

Answer:
```

The brackets `[filename #chunk_index]` are intentional — they tell the LLM the chunk's source, which helps with citations and reduces hallucination ("trust the context, not your memory").

## Why the system prompt is deliberately short

From `basic_rag.py`:

```python
SYSTEM_PROMPT = (
    "You are a helpful assistant. Answer the user's question using the "
    "provided context. If the context is insufficient, say so briefly."
)
```

Hackathon constraint: token comparison must be **fair**. A verbose system prompt ("You are an expert AI researcher with PhD-level knowledge in..." × 200 tokens) inflates Pipeline 2's prompt count vs Pipeline 1 (which has no system prompt). That would falsely make Pipeline 3 look better by comparison.

By keeping it short, the token delta between LLM-Only and Basic RAG reflects **only the retrieved context**.

## Measured behavior

For "Who founded DeepMind, and in what year and city?":

| Metric | Pipeline 1 (LLM-Only) | Pipeline 2 (Basic RAG) |
|---|---|---|
| prompt_tokens | 14 | ~1,580 |
| completion_tokens | ~65 | ~60 |
| total_tokens | ~79 | ~1,640 |
| latency_ms | ~300 | ~9,000 |
| chunks retrieved | 0 | 5 (top-K) |
| Answer correctness | ✅ | ✅ |

**~20× more tokens** for the same correct answer. That's the cost of retrieval. The hackathon's bet is that GraphRAG can give the same answer with way fewer tokens — see [[06 - Pipeline 3 - GraphRAG]].

## Where it can fail

| Failure mode | Cause | Mitigation |
|---|---|---|
| Wrong chunks retrieved | Question wording doesn't embed near right chunks | Use better embedding model, query expansion, hybrid search |
| Right chunks but LLM misreads | Context too noisy or contradictory | Re-rank, smaller top-K, prompt instructions |
| All chunks below threshold | Question is off-topic | Return "I don't know" gracefully |
| Slow | Many chunks + slow LLM | Smaller top-K, faster LLM |

## Why Postgres + JSON arrays, not pgvector?

Honest answer: legacy. The DevRAG project predates this hackathon and already had a Postgres schema with JSON embeddings.

**Could we upgrade?**
- `pgvector` extension: ~10× faster similarity search, native indexing
- Hosted: Pinecone, Weaviate, Qdrant, Chroma
- All would work; none are needed at 9,348 chunks
- 9k chunks × cosine sim in Python ≈ 50ms — fast enough

Upgrading is a defensible choice for scale ≥ 100K chunks. We didn't need to.

## Related

- [[02 - Three Pipelines]] — fairness invariants
- [[03 - Zero Cost Stack]] — why local embeddings + Postgres
- [[06 - Pipeline 3 - GraphRAG]] — the next evolution
- [[08 - Embeddings Deep Dive]] — what 384-d vectors actually mean
- [[13 - Defending The Project]] — common questions

`#pipeline-2` `#vector-search` `#rag`
