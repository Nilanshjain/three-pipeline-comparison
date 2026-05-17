# 14 - Honest Limitations

> [!summary] In one paragraph
> What this project does NOT prove. The most-credible submission is one that scopes its claims precisely — "we showed X on dataset Y under conditions Z" — not one that overclaims and gets torn apart in the Top-10 interview.

## What we actually demonstrated

> *On a 432-article AI/ML Wikipedia corpus (~3M tokens, 6,943 chunks), with Groq Llama 4 Scout 17B as the synthesis LLM across all three pipelines and a 10-question eval set covering single-fact / multi-hop / synthesis categories: a tuned GraphRAG pipeline (combine=True) achieved 90% LLM-as-Judge pass rate at an average of 3,923 honestly-counted tokens per query, versus Basic RAG's 60% pass rate at 1,272 tokens per query.*

That's the precise claim. Everything below scopes what we did NOT prove.

## What this project does NOT prove

### "GraphRAG beats RAG in general"

We tested **one corpus** (AI/ML Wikipedia) with **one knowledge-graph schema** (TigerGraph + LLM extraction). On other domains — customer support tickets, legal docs, scientific papers, code — the result could go either way. Don't generalize beyond what we measured.

### "GraphRAG saves tokens"

It doesn't, in raw terms. Our honestly-counted GraphRAG uses 3× the tokens of Basic RAG. The "token reduction" framing in the hackathon spec is the wrong way to compare these pipelines on our corpus. The right framing is **token cost per unit accuracy** — and there, GraphRAG dominates.

### "Our accuracy numbers are statistically significant"

They aren't. 10 questions is too few. A single judge flip swings us 10pp. The wider standard error is probably ±15pp on any pass-rate we report. In Round 2 we'd go to 100+ questions.

### "The LLM-as-Judge is unbiased"

It's another LLM — Meta-Llama-3.1-8B-Instruct via HuggingFace. It can be inconsistent, lenient on fluent-but-wrong answers, or strict on correct-but-reworded ones. We use BERTScore as a parallel signal but BERTScore has its own failure modes ([[10 - Accuracy Evaluation]]).

### "Same model = fully fair comparison"

We use Llama 4 Scout 17B in all three pipelines' synthesis. But:
- Pipeline 2 embeds with `all-MiniLM-L6-v2` (384-d)
- Pipeline 3 embeds with Gemini `text-embedding-001` (1536-d)
- These are different models with different embedding spaces, contributing to ranking differences beyond just "graph vs vector"

A truly apples-to-apples comparison would use the same embedding model across both retrieval pipelines. We didn't because of constraints in the TigerGraph GraphRAG service.

### "The knowledge graph is high-quality"

It isn't, fully. We have:
- 190 entities for 6,943 chunks (sparse — should be 2,000+)
- 17 garbage entities scrubbed manually (rest are reasonable but could be cleaner)
- 78 communities, level-1 only (richer hierarchical clustering would help synthesis questions)

A complete extraction (with bigger models + more time) would give a denser, cleaner graph. Pipeline 3 might score higher accuracy. Or might overfit and score lower. We don't know.

### "Ingestion cost is amortized"

We report **query-time** tokens. We do NOT report:
- The thousands of LLM calls during entity extraction (one per chunk)
- The community detection + summary calls
- The embedding API calls (free on Gemini's tier but real cost at scale)

A full TCO comparison would include all of these. At low query volume, Basic RAG dominates because GraphRAG's ingestion is a heavy upfront cost. At high query volume, GraphRAG amortizes better. The break-even point depends on per-query cost ratio and traffic — neither of which we modeled.

### "GraphRAG is the right choice for our example use case"

We didn't show this — we showed it's *competitive* on AI/ML Wikipedia. For a real production system, you'd want:
- Per-domain eval set
- Multi-corpus testing
- Cost modeling that includes ingestion
- A vector-only baseline tuned as hard as our GraphRAG was
- Real users, not synthetic questions

## Things we'd want to see before publishing this as a real research result

In rough order:

1. **Wider eval** — 100+ questions across 3+ corpora
2. **Held-out test set** — questions written by people who didn't build the system
3. **Multiple LLM-as-Judges** in committee, with inter-rater agreement
4. **Per-question deep dive** — analyze each wrong answer for failure mode patterns
5. **Cost modeling** — ingestion + query at realistic traffic volumes
6. **Latency at scale** — our latency is single-user; concurrent load behavior unknown
7. **Comparison against a *tuned* Basic RAG** — top-K, re-rankers, query expansion. Our Basic RAG was vanilla.

## Why this disclosure matters

Two audiences:

**Hackathon judges** — especially TigerGraph engineers — will respect intellectual honesty more than overclaim. A submission that says "here are our caveats" is more credible than one that says "we proved GraphRAG > RAG."

**Top-10 product feedback interview** — TigerGraph engineers will probe these exact limitations. Having ready answers ("yes, we know our eval is small; we'd want X to be confident") signals senior engineering judgment.

**The blog post** — should lead with honesty. Title suggestion: *"I built three RAG pipelines side-by-side on AI/ML Wikipedia. Here's what I learned, and here's what I still don't know."*

## What this means for the hackathon submission

| Hackathon claim | Our actual finding | Recommended framing |
|---|---|---|
| Token reduction vs Basic RAG | Negative (we use more) | "GraphRAG trades tokens for accuracy — not a free lunch" |
| Accuracy maintained vs Basic RAG | +30pp improvement | "GraphRAG's headline win" |
| Performance | Mixed | "Groq's LPU lets us run any config fast" |
| Engineering rigor | Strong | "We honestly counted every LLM call; most don't" |

## Related

- [[01 - Hackathon Goal]] — the official metric definitions
- [[10 - Accuracy Evaluation]] — judge + BERTScore caveats
- [[13 - Defending The Project]] — how to handle these limitations under questioning
- [[docs/tuning_results.md]] — the C1/C2/C3 evidence for the accuracy/token tradeoff

`#limitations` `#honesty` `#caveats`
