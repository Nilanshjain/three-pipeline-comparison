# Submission Assets — copy-paste-ready text

All content below is ready to drop into the Unstop submission form, blog post, or social channels. Replace `<YOUTUBE_URL>` and `<BLOG_URL>` with your actual links once published.

---

## 1. Unstop submission form — block by block

### Project name

```
Three Pipelines. Same Model. Every Token Counted.
```

### One-line tagline

```
Same corpus, same model, every LLM call honestly counted: −42.8% tokens on the headline rubric AND the maximum bonus tier (judge ≥90% AND F1_raw ≥0.88) unlocked in the same single eval run.
```

### Short description (~150 words)

```
A side-by-side benchmark of three retrieval-augmented generation pipelines — LLM-Only, Basic RAG, and GraphRAG against TigerGraph Savanna — on a 432-article AI/ML Wikipedia corpus, with all three pipelines using the same synthesis model (Groq Llama 4 Scout 17B) for fair comparison. Every internal LLM call is honestly counted via Docker log scraping, including the upstream GraphRAG service's score_candidate re-rankers most submissions hide.

The same codebase unlocks two distinct hackathon wins via a configuration flag. The default config (C11) achieves −42.8% tokens versus Basic RAG with +7.1pp higher judge accuracy — satisfying the headline rubric. The opt-in C26 config (one flag) stacks adaptive 2-hop graph-traversal fallback + a markdown-trim post-processor + judge self-consistency N=3 voting to unlock the MAXIMUM BONUS TIER: judge 92.9% AND F1_raw 0.891 in the same eval run.

26 configurations tested. 5 reproducible result JSONs. Full engineering frontier documented.
```

### Long description (~600 words — for "explain your approach")

```
"Three Pipelines. Same Model. Every Token Counted." is a side-by-side benchmark of three retrieval-augmented generation pipelines (LLM-Only, Basic RAG, GraphRAG) on a 432-article AI/ML Wikipedia corpus. Built specifically for the TigerGraph GraphRAG Inference Hackathon, with two non-negotiable rules: every pipeline must use the SAME synthesis LLM (so token deltas reflect retrieval strategy, not model choice), and every internal LLM call must be honestly counted (no synthesis-only reporting).

THE HEADLINE WIN (default config C11): GraphRAG uses 805 tokens per query versus Basic RAG's 1,407 — that's −42.8% tokens with maintained accuracy (71.4% judge vs Basic RAG's 64.3%, +7.1pp). The hackathon spec's headline rubric is explicit: "Token reduction only counts if your GraphRAG pipeline maintains or improves accuracy compared to your Basic RAG baseline." C11 satisfies both. The config: method=community, top_k=1, with_chunk=True, combine=True — hierarchical retrieval where a pre-LLM-summarized community provides global context and a single anchoring chunk supplies specifics.

THE MAXIMUM BONUS TIER (opt-in config C26): judge ≥90% AND F1_raw ≥0.88 in the SAME eval run. The hackathon's bonus rule requires both criteria simultaneously. C26 hits judge 92.9% and F1_raw 0.891, reproducible from accuracy_results_C26_FINAL.json. Three engineering pieces stack to unlock it: (1) an adaptive 2-hop graph-traversal fallback — when the cheap community-summary primary returns a refusal phrase, retry with num_hops=2, top_k=5 hybrid retrieval to walk entity edges and surface multi-hop facts the vector match misses (fixes Q6 Sutskever↔Hinton PhD link, Q14 Fei-Fei Li↔ImageNet creation); (2) a textual _trim_answer post-processor that strips upstream LLM markdown headers and cuts at next section break — zero LLM cost, pushes F1_raw from 0.86 to 0.89 by matching reference-answer style; (3) judge self-consistency N=3 majority voting (Wang et al 2022) that compensates for the HuggingFace Inference backend silently ignoring the `seed` parameter (observed ±20pp per-call variance on borderline answers).

ENGINEERING DEPTH: 26 configurations tested across the token-vs-accuracy frontier. Five reproducible result JSONs on disk (C2, C11, C18b, C19, C24, C26 FINAL variants). Honest token accounting via Docker container log scraping captures every score_candidate LLM call most teams miss (the upstream service fires ~14 calls per query by default; reporting only the synthesis prompt under-reports cost by 13×). Full failure log of 11 distinct walls in docs/notes/11 - Failures and Learnings.md.

WHAT THIS DOES NOT CLAIM: tested one corpus (results may flip on legal docs or sparse-relationship papers); same config does not win both rubrics simultaneously (C11 for tokens, C26 for max bonus — both ship); Q12 (LSTM/RNN) is the lone persistent failure where the community summary confidently returns the wrong architecture and no refusal phrase catches it; 14 questions is too few for tight error bars.

STACK: TigerGraph Savanna (cloud) + Docker GraphRAG service + FastAPI backend (Python) + React frontend (dashboard with per-question deep-dive). Synthesis via Groq Llama 4 Scout 17B (500K TPD free). Pipeline 2 embeddings via sentence-transformers all-MiniLM-L6-v2 (local). Pipeline 3 embeddings via Gemini text-embedding-001 (1K RPD free). LLM-as-Judge via Meta-Llama-3.1-8B-Instruct on HuggingFace Inference. Everything fits in free tiers — zero per-month cost.
```

### Key results table (for any "results" field)

```
HEADLINE RUBRIC (C11 default config):
- 805 tokens/query vs Basic RAG's 1,407 → -42.8% tokens
- 71.4% judge accuracy vs Basic RAG's 64.3% → +7.1pp
- File: accuracy_results_C11_FINAL.json

MAXIMUM BONUS TIER (C26 opt-in config):
- judge 92.9% (13/14 pass) → ≥90% bonus criterion MET
- F1_raw 0.891 → ≥0.88 bonus criterion MET
- Both in SAME run → MAXIMUM BONUS UNLOCKED
- File: accuracy_results_C26_FINAL.json

All 3 pipelines use same Llama 4 Scout 17B for synthesis (fair comparison).
All numbers reproducible via `python tests/accuracy_eval.py` against the live API.
```

### Links

```
GitHub repo: https://github.com/Nilanshjain/DevRAG
Demo video: <YOUTUBE_URL>
Blog post: <BLOG_URL>
Documentation:
  - README: https://github.com/Nilanshjain/DevRAG/blob/main/README.md
  - Tuning frontier: https://github.com/Nilanshjain/DevRAG/blob/main/docs/tuning_results.md
  - Architecture: https://github.com/Nilanshjain/DevRAG/blob/main/docs/architecture.md
  - Blog: https://github.com/Nilanshjain/DevRAG/blob/main/docs/blog_post.md
```

### "What makes this stand out" (if asked)

```
1. Honest token accounting via Docker log scraping — captures all ~14 internal LLM calls per query, not just the synthesis prompt. Most submissions will under-report GraphRAG's cost by 13×.

2. Both the headline rubric AND the maximum bonus tier achieved in the same codebase — selectable via one config flag. Most submissions optimize for one or the other.

3. 26-configuration tuning frontier with five reproducible result JSONs — every milestone config (C2, C11, C18b, C19, C24, C26) has a saved eval JSON on disk for the judges to verify.

4. Research-backed engineering with citations: Microsoft GraphRAG "From Local to Global" (arxiv 2404.16130) for graph traversal, Wang et al 2022 self-consistency (arxiv 2203.11171) for judge variance reduction, Gao et al 2022 HyDE (arxiv 2212.10496) and Press et al 2022 Self-Ask (arxiv 2210.03350) as future-extension hooks.

5. Honest about limitations: Q12 (LSTM vs RNN) is the lone persistent failure, documented openly with the proposed CoVe fix. Token cost of C26 (~2,500/q) is explicitly NOT a token win — it's the accuracy-bonus config. Different configs serve different rubrics; we don't pretend one config does it all.
```

---

## 2. Twitter / X post (≤280 chars)

### Option A — lead with max bonus

```
Just shipped my @TigerGraph GraphRAG Hackathon submission. 

26 configs tested. Maximum bonus tier unlocked: judge 92.9% AND F1_raw 0.891 in the same run ✅. Default config also wins the headline rubric: -42.8% tokens vs Basic RAG.

#GraphRAGInferenceHackathon

[link]
```

### Option B — lead with the engineering discovery

```
Built a 3-pipeline RAG benchmark for the @TigerGraph Hackathon — and discovered the HF Inference judge silently ignores the `seed` parameter. ±20pp run-to-run variance.

Self-consistency N=3 voting fixed it. Maximum bonus tier unlocked.

#GraphRAGInferenceHackathon

[link]
```

### Option C — concise win statement

```
🏆 @TigerGraph GraphRAG Hackathon submission shipped.

✅ -42.8% tokens vs Basic RAG (headline rubric)
✅ Judge 92.9% + F1_raw 0.891, same run (MAX BONUS tier)

26 configs tested. Every internal LLM call honestly counted.

#GraphRAGInferenceHackathon

[link]
```

---

## 3. LinkedIn post (longer, ~150-200 words)

```
Just shipped my submission to the @TigerGraph GraphRAG Inference Hackathon.

The challenge: prove GraphRAG beats vector-only RAG by using fewer tokens AND maintaining accuracy. Easy to claim, hard to do honestly.

Two wins from the same codebase:

🥇 Headline rubric (default config): GraphRAG uses 805 tokens/query vs Basic RAG's 1,407 — that's -42.8% tokens, with +7.1 percentage points higher judge accuracy.

🏆 Maximum bonus tier (one flag): judge ≥90% AND F1_raw ≥0.88 in the SAME single eval run. Hit judge 92.9% + F1_raw 0.891.

The path required stacking three engineering pieces:
• 2-hop graph traversal fallback for multi-hop entity questions (Microsoft GraphRAG "From Local to Global" pattern)
• A 30-line text post-processor that strips upstream LLM markdown — boosted F1 by 3pp with zero LLM cost
• Judge self-consistency N=3 voting (Wang et al 2022) to compensate for HuggingFace Inference silently ignoring the `seed` param

Honest counting matters: the GraphRAG service fires ~14 LLM calls per query by default. Reporting only the synthesis prompt hides 13× the real cost. My pipeline scrapes Docker logs to count everything.

26 configurations tested. 5 reproducible result JSONs on disk. Full write-up + code:

[GitHub link]

#GraphRAGInferenceHackathon #RAG #KnowledgeGraphs #TigerGraph
```

---

## 4. Email/DM template (if reaching out to TigerGraph team or judges)

```
Subject: TigerGraph GraphRAG Hackathon — "Three Pipelines. Same Model. Every Token Counted." submission

Hi [name],

I wanted to share my submission to the TigerGraph GraphRAG Inference Hackathon — a side-by-side benchmark of three RAG pipelines built on the rule that all three use the same synthesis model and every internal LLM call is honestly counted. 26 configurations tested.

Two key results:

1. Headline rubric satisfied: GraphRAG (default config) uses -42.8% tokens vs Basic RAG with +7.1pp higher judge accuracy.

2. Maximum bonus tier unlocked: judge 92.9% AND F1_raw 0.891 in the same eval run, via adaptive 2-hop graph-traversal fallback + markdown-strip post-processor + judge self-consistency N=3 voting.

Everything reproducible from saved JSONs in the repo. Full engineering progression documented across docs/tuning_results.md.

GitHub: https://github.com/Nilanshjain/DevRAG
Demo: <YOUTUBE_URL>
Blog: <BLOG_URL>

Happy to chat about the technical details or any questions during judging.

Best,
Nilansh
```

---

## 5. Suggested submission order

1. **Pre-publish (do these first)**: blog post on Medium/Dev.to/Hashnode → get the public URL
2. **Record + upload demo video** → get YouTube unlisted URL
3. **Final `git commit + git push`** with all docs locked
4. **Fill Unstop form** using the blocks above, with all 3 URLs in hand
5. **Post on Twitter + LinkedIn** with the GitHub + blog + video links
6. **Tag** `@TigerGraph` + `#GraphRAGInferenceHackathon` on all social posts

Don't post on social BEFORE submitting on Unstop — keeps everything in order for the judges.
