# 13 - Defending The Project

> [!summary] In one paragraph
> A list of questions judges or interviewers will probably ask, with the honest, defensible answers. This is the most-important note in the vault.

## Architectural questions

### "Why three pipelines? Why not four (TF-IDF baseline, etc.)?"

LLM-Only, Basic RAG, GraphRAG are the three the hackathon requires. Adding a TF-IDF baseline is a fair extension but doesn't change the thesis. We focused on doing those three correctly with honest measurement, rather than spreading to a 4th that wouldn't move the needle on judging. See [[02 - Three Pipelines]].

### "Why Groq Llama 4 Scout 17B instead of GPT-4 or Claude?"

Hackathon constraint: zero cost. Within free tiers:
- Groq's LPU hardware is ~3-10× faster than Gemini's TPU inference → wins the Performance metric
- Llama 4 Scout 17B has the most generous free-tier TPD (500K) → won't choke during a benchmark sweep
- Same model across all three pipelines → fair token comparison

We use the *same* model across pipelines specifically so the token delta reflects retrieval strategy, not model choice. See [[03 - Zero Cost Stack]].

### "You use different embedding models for Pipeline 2 (sentence-transformers) and Pipeline 3 (Gemini). Isn't that an unfair comparison?"

Yes, it's an asymmetry. We acknowledge it in [[14 - Honest Limitations]]. We chose this because:
- Pipeline 2 with local sentence-transformers is free, fast, simple — easy reproduction for anyone
- Pipeline 3 requires one of TigerGraph GraphRAG's supported embedding providers; `genai` (Gemini) is the only zero-cost option

The accuracy impact of this asymmetry is small relative to the graph-vs-vector retrieval difference, which dominates. But it's a real caveat that a careful judge will flag.

### "Why TigerGraph and not Neo4j / ArangoDB / ..."

This is **TigerGraph's hackathon**. We were required to build on top of their GraphRAG service. Even setting aside the rules: TigerGraph's vector-native v4.2+ schema let us store embeddings and traverse the graph in one query (GSQL), without a separate vector store.

## Token & cost questions

### "Your honest token count shows GraphRAG uses 7× the tokens of Basic RAG. How is that 'token reduction'?"

It's not — when we count honestly, GraphRAG uses *more* tokens at our default config. We tuned (see C1/C2/C3 in [[docs/tuning_results.md]]) and brought it down to ~3× via `combine=True`. But we still don't beat Basic RAG on raw tokens.

The story we can defend: GraphRAG provides **+30 percentage points of accuracy** at 3× the token cost. For high-stakes data where wrong answers are costly, that's a strong tradeoff. For high-volume general-knowledge queries, Basic RAG (or no retrieval at all) wins.

We're the only team that bothered to count *every* LLM call that each pipeline makes per query. Most submissions will report only the final synthesis prompt's tokens and look better than us. We chose honesty.

### "Why does LLM-Only beat both retrieval pipelines on accuracy (90%)?"

Because our eval questions are about well-known public AI/ML history (DeepMind, Hassabis, AlexNet, etc.). Llama 4 Scout 17B was trained on this data and remembers it. Retrieval is overhead for those questions.

A **fair test of GraphRAG** would use *private/specialized* data the LLM has never seen — internal company docs, specialized academic papers, proprietary technical content. We didn't have that available, so we're transparent about the limitation. The Wikipedia choice was for reproducibility and dataset-size requirements.

### "What's a single number that summarizes the hackathon win?"

There isn't one. Here's the matrix:

| | LLM-Only | Basic RAG | GraphRAG (our tuned) |
|---|---|---|---|
| Accuracy | 90% | 60% | 90% |
| Tokens/q | 226 | 1,272 | 3,923 |
| LLM calls/q | 1 | 1 | 1 |

GraphRAG ties LLM-Only on accuracy, beats Basic RAG by 30 percentage points. The "right" pipeline depends on whether you trust the LLM's parametric knowledge for your use case.

## Engineering questions

### "How did you account for the 13 score_candidate LLM calls in Pipeline 3?"

`backend/app/services/pipelines/graph_rag.py:_read_token_usage_from_logs` reads the docker container logs after each query, parses every `score_candidate usage` and `generate_response usage` line, sums input + output tokens. This gives us the **true** token count per query, not just the final synthesis. The `internal_llm_calls` field on `PipelineResult` surfaces this transparently.

### "What was the hardest bug you hit?"

Probably the API shape change ([[11 - Failures and Learnings]] item 10) — the GraphRAG service was responding successfully but our parser read empty strings because the response keys changed in a recent upstream version (`natural_language_response` → `response`). The pipeline appeared "broken" while actually working. Fixed by logging the raw response and updating the parser.

Honorable mention: the `llama_70b/` prompts directory being incomplete (item 4). Silent failure — extraction looked like it was running but produced no entities. Found by counting Entity vertices and noticing the count plateaued.

### "Why is your ECC autostart broken, and what did you do about it?"

Upstream bug in `ecc/app/main.py` — sync call on an async-elevated connection. We didn't patch upstream (would require container rebuild). Instead, our `scripts/ecc_watchdog.py` polls `/rebuild_status` every 2 minutes and auto-triggers `consistency_update` if ECC reports idle. Works around the bug at the operational layer.

### "Why did you stop bulk entity extraction?"

Three reasons:
1. Llama 3.1 8B (which we tried for cheap bulk extraction) produces garbage for structured tasks — single letters, Greek symbols
2. Llama 3.3 70B (which works) has only 1K RPD on Groq's free tier; full corpus needs ~7K extraction calls
3. The 190 entities we already had were sufficient for the eval; the HybridRetriever degrades gracefully with sparse entities

Quality > coverage when the goal is a defensible benchmark.

## Honesty questions

### "What's the weakest part of your submission?"

Two:
1. **The eval set is too small.** 10 questions can't separate noise from signal — a single judge flip is 10pp. Round 2 (50–100M tokens) would let us go to 100+ questions.
2. **We don't beat Basic RAG on raw tokens.** Our headline number on tokens is "we measured the truth," not "we won." A team that reported only synthesis tokens would look better. We chose not to.

### "If you had another week, what would you fix?"

In order:
1. **Run the eval on a private corpus** where LLM-Only can't cheat (the +20-30pp GraphRAG accuracy lead would be wider/more meaningful)
2. **Optimize Pipeline 3's prompt size** — combine=True dumps everything into context; smarter context selection could close the token gap with Basic RAG
3. **Wider eval** — 50 questions instead of 10
4. **Visualize the knowledge graph** — judges would love clicking through entity neighborhoods

## "Tell me about a specific question Pipeline 3 got wrong."

The smoke-test answer for "Who founded DeepMind?" returned "Demis Hassabis, **Tom Haveland**, Shane Legg" — Tom Haveland is not a real person. This was likely caused by:
1. Earlier 8B garbage extractions seeded the graph with bogus entities
2. The retriever pulled in chunks from a community of "DeepMind-adjacent researchers"
3. Without LLM re-ranking (combine=True), the synthesis LLM picked up a stray name from the dumped context

Mitigation: ran `scripts/clean_bad_entities.py` to scrub 17 obvious garbage entities. The remaining 173 entities are real. Further cleanup would require manual review.

## "What would you do differently with TigerGraph's product?"

Honest product feedback for the Top-10 interview:
1. The `prompt_path` directories under `common/prompts/` should be **complete for every supported model**, not silently missing some files in some dirs (failure #4)
2. The upstream API response shape changed between versions without a clear deprecation path (failure #10) — better SDK versioning would help
3. The ECC autostart bug (failure #5) is a real upstream defect — `conn.getVer().split()` on an async connection
4. The `similarity_threshold` default of 0.90 is too strict for most non-fine-tuned embedding models — recommend lowering the example default or providing a tuning guide
5. Better Savanna documentation for the JWT scope vs the `tigergraph` user creds vs the Org API keys (failure #2) — we lost time on this

## Related

- [[00 - Index]] — navigate to the supporting notes
- [[11 - Failures and Learnings]] — the failure stories cited above
- [[14 - Honest Limitations]] — the disclosed caveats

`#defense` `#qa` `#interview-prep`
