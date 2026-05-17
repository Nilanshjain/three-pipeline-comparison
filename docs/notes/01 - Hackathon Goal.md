# 01 - Hackathon Goal

> [!summary] In one sentence
> Build three RAG pipelines side-by-side and use a fair benchmark to show GraphRAG reduces tokens vs Basic RAG without losing answer accuracy.

## What problem does this solve?

LLMs consume **tokens** for every API call. A token is roughly ¾ of a word — Anthropic, OpenAI, Google all bill by tokens. Companies running LLMs in production pay per token, every query, every day.

When you ask an LLM a complex question over your private data, the standard pattern is **Retrieval-Augmented Generation (RAG)**:

1. Embed the question into a vector
2. Search a database for the most similar chunks of your data
3. Stuff those chunks into the prompt as "context"
4. Send the giant prompt to the LLM
5. Get an answer

The problem: step 3 inflates token usage by 5-50×. Every retrieval pulls in *similar* text, but "similar" ≠ "relevant for reasoning across entities and relationships." Vector search finds chunks that mention the same words; it can't *reason* about how concepts connect across documents.

**GraphRAG** is the proposed fix. Instead of just retrieving similar chunks, you also build a **knowledge graph** of entities (people, places, concepts) and relationships between them. At query time, you retrieve a *focused subgraph* relevant to the question — fewer tokens, more reasoning power.

The hackathon's bet: GraphRAG beats Basic RAG on **token usage** without losing **answer accuracy**.

## What we have to deliver

From `GraphR.txt` (the hackathon spec):

| Requirement | Where it lives in our repo |
|---|---|
| 3 pipelines (LLM-Only, Basic RAG, GraphRAG) | `backend/app/services/pipelines/` |
| Comparison dashboard (1 query → 3 answers + metrics) | `frontend/src/pages/Compare.jsx` |
| Dataset of ≥ 1M tokens of text | `data/raw_articles/` — 432 Wikipedia articles ≈ 3M tokens |
| Tokens, latency, cost, accuracy per pipeline | `backend/app/api/benchmark.py` + `backend/tests/accuracy_eval.py` |
| LLM-as-Judge + BERTScore accuracy eval | `backend/app/services/accuracy.py` |
| Architecture diagram | (to be drawn — Mermaid in [[12 - Repo Tour]]) |
| Demo video, blog post, public GitHub | TBD |

## How we're judged (and what this means for choices)

| Criterion | Weight | What we optimize for |
|---|---|---|
| **Token reduction** | 30% | Make GraphRAG's prompts shorter than Basic RAG's at equal accuracy |
| **Answer accuracy** | 30% | Maintain ≥90% LLM-as-Judge pass rate, BERTScore F1 rescaled ≥0.55 |
| **Performance** | 20% | Fast end-to-end latency; Groq's LPU helps here |
| **Engineering & storytelling** | 20% | Clean code, working dashboard, honest blog post |

Bonus points: ≥90% judge pass rate **and** BERTScore F1 ≥ 0.55 → max bonus.

This drives several decisions:
- Same LLM across all 3 pipelines → fair token comparison (model-agnostic delta) — see [[03 - Zero Cost Stack]]
- Test on 10 questions covering single-fact, multi-hop, and synthesis types → see [[10 - Accuracy Evaluation]]
- Use Groq for speed (LPU hardware) → wins Performance even with parity on quality

## The honest framing

Hitting the metrics doesn't *prove* "GraphRAG beats RAG" in general. It proves it on **our specific corpus with our specific tuning and our specific eval set of 10 questions.** That's a defensible data point — not a research result. See [[14 - Honest Limitations]].

Why this matters: in the **Top-10 product feedback interview**, TigerGraph engineers will probe how well you understand the tradeoffs. Overclaiming sinks credibility. Underselling wastes the work.

## Related

- [[02 - Three Pipelines]] — the technical structure that satisfies these requirements
- [[03 - Zero Cost Stack]] — the constraints we worked within
- [[13 - Defending The Project]] — anticipated questions from judges

`#hackathon` `#problem-statement`
