# 03 - Zero Cost Stack

> [!summary] The decision
> Groq Llama 3.3 70B for all completion, Gemini `text-embedding-001` for graph embeddings, local sentence-transformers for Basic RAG embeddings, HuggingFace free-tier Llama-3.1-8B for the LLM-as-Judge. All within free tiers.

The hackathon doesn't pay for our infrastructure. We targeted **$0 / month** for Round 1. Here's how each piece was chosen.

## Completion LLM: Groq Llama 3.3 70B Versatile

### Why Groq?

| Provider | Speed | Free tier | Why or why not |
|---|---|---|---|
| **Groq** | ~250 tok/sec (LPU hardware) | 30 RPM / 1K RPD / 12K TPM | ✅ Fastest by 3-10×, wins Performance metric |
| Gemini 2.5 Pro | ~80 tok/sec | Not free; $1.25/$10 per 1M | ❌ Paid only |
| Gemini 2.5 Flash | ~80 tok/sec | 10 RPM / 250 RPD | ❌ Tighter free tier than Groq |
| OpenAI GPT-4 | ~50 tok/sec | None | ❌ No free tier |

Groq runs LLMs on custom **LPU (Language Processing Unit)** hardware — purpose-built for transformer inference, drastically faster than GPUs for this workload. For the hackathon's Performance metric (20% of judging), this is a big lever.

### Why Llama 3.3 70B specifically?

Available on Groq free tier, models ranked roughly:

| Model | LMArena rank | Multi-hop reasoning | Notes |
|---|---|---|---|
| Llama 3.3 70B Versatile | ~1255 | Strong | ✅ Chosen |
| Llama 3.1 8B Instant | ~1170 | Weak | Failed our entity extraction — see [[11 - Failures and Learnings]] |
| Qwen 3 32B | ~1245 | Strong | Considered as fallback |

The 70B is comparable to Gemini 2.5 Flash on quality benchmarks. It handles multi-hop questions (Q5–Q10 in our eval) which weaker models fall apart on.

### Why same model across all 3 pipelines?

This is the **fairness invariant** in [[02 - Three Pipelines]]. If Pipeline 1 used GPT-4 and Pipeline 3 used Llama, you couldn't tell whether token differences came from retrieval strategy or model behavior. By forcing the same model, the **token delta is purely retrieval-driven** — exactly what the hackathon judges.

In code: `backend/app/services/llm_client.py` is a thin abstraction that all three pipelines call. Provider and model are env vars (`LLM_PROVIDER=groq`, `LLM_MODEL=llama-3.3-70b-versatile`), so swapping is one config change.

## Embeddings: split decision

### Basic RAG embeddings: local sentence-transformers `all-MiniLM-L6-v2`

- **Free.** Runs on CPU locally, no API calls.
- 384-dimensional vectors (smaller than transformer-based ones).
- Good enough for similarity over English text.
- Lives in `backend/app/services/embeddings.py`.

### GraphRAG embeddings: Gemini `text-embedding-001`

- Free tier: 1,000 requests/day. **This bit us** — see [[11 - Failures and Learnings]].
- 1536-dimensional vectors.
- Required because the TigerGraph GraphRAG service supports a fixed set of embedding providers, and `genai` (Gemini) is the only fully-free option in that list.

This asymmetry is honest to disclose — Basic RAG and GraphRAG use different embedding models, so retrieval *quality* differs slightly beyond just "graph vs no graph." See [[14 - Honest Limitations]].

## Graph database: TigerGraph Savanna

### Why TigerGraph?

The hackathon is **TigerGraph's hackathon**. The official GraphRAG service stack runs on TigerGraph. Using anything else (Neo4j, etc.) would fail the judging criterion "built on top of the TigerGraph GraphRAG repo."

### Why Savanna and not Community Edition (local)?

- Savanna gives **~$60 in free credits** instantly via tgcloud.io.
- Cloud-hosted, no local install pain.
- Same TigerGraph engine under the hood, just managed.
- For Round 2 (Top-10), TigerGraph provides $50 Gemini credits — assumes Savanna setup.

Tradeoff: Savanna workspaces idle-suspend, and our local Docker can't see Savanna's filesystem. Both required workarounds — see [[11 - Failures and Learnings]] and [[06 - Pipeline 3 - GraphRAG]].

## Vector store for Basic RAG: PostgreSQL with JSON

### Why Postgres?

- **Free, runs locally.**
- The previous DevRAG project already had a PostgreSQL setup with `vector_documents` table.
- Stores embeddings as JSON arrays. Not pgvector — we do cosine similarity in Python.

### Why not pgvector / Pinecone / Weaviate / Qdrant?

- All worked in principle. Postgres + JSON was already there.
- For 9,348 chunks (current size), in-process cosine similarity in Python is fast enough (~50ms per query).
- Upgrading to pgvector would buy ~10× speed but adds setup complexity. Not needed at this scale.

## LLM-as-Judge: HuggingFace Inference Llama-3.1-8B-Instruct

For accuracy eval, we need a **second** model to grade Pipeline answers. Free options:

| Option | Cost | Why or why not |
|---|---|---|
| **HuggingFace Inference Providers** | Free credit each month | ✅ Chosen — official upstream pattern |
| Groq Llama 3.1 8B | Free | ❌ Same provider as pipelines = potential self-grading bias |
| GPT-4 via OpenAI | Paid | ❌ Not free |
| BERTScore alone | Free, local | ⚠️ Used as second metric, but not a true accuracy proxy |

We use both LLM-as-Judge AND BERTScore — see [[10 - Accuracy Evaluation]] for why two metrics matter.

## The cost ledger

After all decisions:

| Component | Provider | Monthly cost |
|---|---|---|
| Pipelines 1+2+3 completion (Llama 3.3 70B) | Groq | $0 (free tier) |
| Basic RAG embeddings | sentence-transformers (local) | $0 |
| GraphRAG embeddings | Gemini `text-embedding-001` | $0 (free tier) |
| Knowledge graph storage | TigerGraph Savanna | ~$60 credits, then $0 if under usage limits |
| Vector store | PostgreSQL local | $0 |
| LLM-as-Judge | HuggingFace Inference | $0 (free tier credit) |
| BERTScore | local Python package | $0 |
| **Total** | | **$0** |

## Defending these choices

> *"Why not just pay for GPT-4? It would be more accurate."*

Hackathon constraint: zero cost. The model-equality invariant matters more than raw model strength — if we paid for GPT-4 for Pipeline 3 only, we'd be comparing model choices, not retrieval strategies.

> *"Groq's free tier is restrictive — won't you hit rate limits?"*

Yes, we did. See [[11 - Failures and Learnings]]. The 1,000 RPD ceiling on Llama 3.3 70B is the real wall during ingestion. We worked around it by limiting bulk extraction to focused subsets — quality where it matters, not raw coverage.

> *"Why local sentence-transformers for one pipeline and Gemini for the other?"*

Forced by the TigerGraph GraphRAG service's embedding-provider list. Acknowledged as an asymmetry in [[14 - Honest Limitations]]. We could have used Gemini for both to be fully consistent — but Basic RAG via Postgres-only is simpler and faster locally.

## Related

- [[02 - Three Pipelines]] — what each pipeline uses these for
- [[04 - Pipeline 1 - LLM Only]] — uses Groq completion only
- [[05 - Pipeline 2 - Basic RAG]] — uses Groq + sentence-transformers + Postgres
- [[06 - Pipeline 3 - GraphRAG]] — uses Groq + Gemini embeddings + TigerGraph
- [[11 - Failures and Learnings]] — the rate-limit walls these decisions hit

`#stack` `#decisions` `#zero-cost`
