# 00 - Index

> [!info] How to use this vault
> Drop this folder into any Obsidian vault. Notes are wiki-linked with `[[Note Name]]`. Read in numbered order the first time; jump around after.

This vault explains the **TigerGraph GraphRAG Inference Hackathon** entry built in `H:/tigergraph-hack/`. The goal: prove that **graphs make LLM inference faster, cheaper, and smarter than vector-based RAG alone**, by building three pipelines side-by-side and letting the numbers tell the story.

## Read these in order

1. [[01 - Hackathon Goal]] — what we're trying to prove and why anyone cares
2. [[02 - Three Pipelines]] — the central abstraction every other note builds on
3. [[03 - Zero Cost Stack]] — Groq, Gemini, TigerGraph, Postgres — why each
4. [[04 - Pipeline 1 - LLM Only]] — the baseline (no retrieval)
5. [[05 - Pipeline 2 - Basic RAG]] — vector search + LLM (the industry standard today)
6. [[06 - Pipeline 3 - GraphRAG]] — knowledge graph + multi-hop reasoning
7. [[07 - Knowledge Graph Schema]] — what TigerGraph stores and why
8. [[08 - Embeddings Deep Dive]] — what "1536-dimensional vector" actually means
9. [[09 - Benchmark Harness]] — how we make the comparison fair
10. [[10 - Accuracy Evaluation]] — LLM-as-Judge + BERTScore
11. [[11 - Failures and Learnings]] — every wall we hit (this is most of the engineering story)
12. [[12 - Repo Tour]] — file-by-file map
13. [[13 - Defending The Project]] — Q&A you'll actually be asked
14. [[14 - Honest Limitations]] — what we'd do differently with more time

## At a glance

| Component | Files | One-line role |
|---|---|---|
| Backend | `backend/app/` | FastAPI server running all 3 pipelines in parallel |
| LLM-Only pipeline | `backend/app/services/pipelines/llm_only.py` | Question → Groq Llama 3.3 70B → answer (no retrieval) |
| Basic RAG | `backend/app/services/pipelines/basic_rag.py` | Question → embed → search Postgres → LLM with chunks |
| GraphRAG | `backend/app/services/pipelines/graph_rag.py` | Question → TigerGraph hybrid retriever → LLM with graph context |
| Benchmark API | `backend/app/api/benchmark.py` | Runs all 3 in parallel, returns side-by-side metrics |
| Dashboard | `frontend/src/pages/Compare.jsx` | One query in, three answers + tokens/latency/cost out |
| GraphRAG service | `infra/graphrag-deploy/` | Docker stack running `tigergraph/graphrag` against Savanna |
| Dataset | `data/raw_articles/` | 432 Wikipedia AI/ML articles (~3M tokens) |
| Accuracy eval | `backend/tests/accuracy_eval.py` | Runs 10 questions through all pipelines, grades each |

## The headline result we're aiming for

> *"On a 3M-token AI/ML Wikipedia corpus, GraphRAG used X% fewer tokens than Basic RAG while matching or exceeding its accuracy on a 10-question eval."*

That is **a single defensible data point** in favor of the GraphRAG thesis — not "GraphRAG > RAG, QED." See [[14 - Honest Limitations]] for why the framing matters.

## Tags

`#hackathon` `#rag` `#graphrag` `#tigergraph` `#groq` `#gemini`
