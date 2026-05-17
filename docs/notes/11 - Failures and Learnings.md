# 11 - Failures and Learnings

> [!summary] In one paragraph
> Eleven distinct failure modes hit during this build. Each one cost time, taught a real lesson, and informed a defensible architectural choice. This is the engineering story that distinguishes a thoughtful submission from a "ran the tutorial" submission.

Pipelines 1 and 2 each took ~1 hour. Pipeline 3 took the rest of the project. These are the walls.

## The full failure log (chronological)

### 1. Savanna workspace auto-suspends

**Symptom**: GraphRAG container crashed at startup with `500 Server Error: Failed to start workspace. Auto start is not enabled.`

**Root cause**: TigerGraph Savanna workspaces idle out after inactivity to save cloud cost. Default has Auto Start disabled.

**Fix**: enable Auto Start in workspace settings on tgcloud.io. Manual start required first time.

**Lesson**: cloud-managed services have idle policies. If your container expects an always-on backend, configure auto-wake or write a watchdog.

### 2. Graph-scoped apiToken can't install GDS

**Symptom**: GraphRAG container logged `Access Denied: The input token belongs to graph Nilanshgraph, but it is attempting operations on global`.

**Root cause**: The `Installing GDS library` step needs **global** scope. The user's apiToken was generated with `graph: "Nilanshgraph"` scope only.

**Fix**: Generate a fresh secret via Admin Portal → Management → Users → My Profile → Secrets. Then exchange via `POST /gsql/v1/tokens` with no `graph` field in the body. Result: a JWT with `"graph": ""` (global scope).

**Lesson**: token scopes matter. Always decode JWTs (jwt.io) to verify scope before assuming creds work.

### 3. `text-embedding-004` deprecated

**Symptom**: `GoogleGenerativeAIError: Error embedding content: 404 models/text-embedding-004 is not found for API version v1beta`.

**Root cause**: Google deprecated the `text-embedding-004` model. The upstream `server_config.json` example referenced it.

**Fix**: Use `models/gemini-embedding-001` (text-only, stable, 1536-d default). The newer `gemini-embedding-2` works too (3072-d default).

**Lesson**: API endpoints/models can deprecate silently. Always verify model names against current vendor docs.

### 4. `llama_70b/` prompts directory is incomplete

**Symptom**: Entity extraction silently failed with `"Invalid template: None"` for every chunk. Embeddings worked, chunks landed in TG, but **zero Entity vertices** were being created.

**Root cause**: We had `prompt_path: "./common/prompts/llama_70b/"` because we use a Llama model. But that directory ships only 2 prompt files in the upstream image, missing the critical `entity_relationship_extraction.txt`, `chatbot_response.txt`, `community_summarization.txt`, etc.

**Fix**: Use `./common/prompts/openai_gpt4/` regardless of which LLM you actually use. The prompts are generic enough that any instruction-tuned LLM handles them.

**Lesson**: don't assume the directory named after your model is complete. Verify file inventory.

### 5. ECC autostart has an async/sync bug

**Symptom**: After setting `enable_consistency_checker: true` and `graph_names: ["Nilanshgraph"]`, ECC started briefly then crashed with `'coroutine' object has no attribute 'split'`.

**Root cause**: Upstream bug in `ecc/app/main.py` — calls `conn.getVer().split(".")` synchronously on an async-elevated connection. The async coroutine doesn't have `.split()`.

**Workaround**: Don't rely on auto-start. After every container restart, manually trigger ECC via:
```
GET http://localhost:8801/Nilanshgraph/graphrag/consistency_update
Auth: Basic tigergraph:tigergraph
```
The on-demand endpoint uses a different connection-setup path and works fine. We built `scripts/ecc_watchdog.py` to auto-trigger if ECC ever stops.

**Lesson**: when upstream has a bug, sometimes you patch around it instead of into it. Document the workaround so the team isn't re-debugging next time.

### 6. Savanna can't read local Docker filesystems

**Symptom**: `POST /supportai/ingest` returned `SemanticException: The datasource 'DocumentContent' cannot be found.`

**Root cause**: The upstream "local" data source mode runs `RUN LOADING JOB USING $DocumentContent:<path>` where `<path>` is the graphrag container's filesystem. **Savanna's cloud TigerGraph can't see that filesystem** — different VPCs, different worlds.

**Fix**: Stream each document directly to TG over REST++ via `pyTigerGraph.runLoadingJobWithData(payload, "DocumentContent", "load_documents_content_json")`. One HTTP POST per document. The upstream BDA/S3 code path uses this same pattern (`supportai.py:668`). See `scripts/ingest_graphrag.py:stream_documents()`.

**Lesson**: cloud services need APIs, not filesystems. Match your ingest pattern to what the backend can actually reach.

### 7. Llama 3.1 8B produces garbage entities

**Symptom**: After fixing prompts (failure 4), 8B-based entity extraction produced entities like single letters (`t`, `d`, `a`), Greek symbols (`π`, `τ`), and URL fragments. ~17% pollution rate.

**Root cause**: The extractor uses LangChain's `LLMGraphTransformer` which relies on function-calling / tool-use. Llama 3.1 8B is weaker at structured tool-call output than larger models. Even when the JSON is valid, the entity *content* is degenerate.

**Workaround**: 
- Use **Llama 3.3 70B** for entity extraction (better tool-use adherence) — but blew through Groq's 1K RPD limit
- OR clean up bad entities after the fact (see `scripts/clean_bad_entities.py`)

**Lesson**: small models fail at structured tasks, not (just) at general generation. If you need reliable JSON, use a bigger model OR a model specifically tuned for tool-use.

### 8. Groq Llama 3.3 70B daily TPD = 100K tokens

**Symptom**: After hours of ECC bulk re-extraction, every query hit `429: Rate limit reached for model llama-3.3-70b-versatile ... on tokens per day (TPD): Limit 100000, Used 100000`.

**Root cause**: Groq's free tier has both TPM (per-minute) and TPD (per-day) limits. We blew through TPD because the ECC re-extraction was eating ~5K tokens per chunk × thousands of chunks.

**Fix**: 
- Switched to **Llama 4 Scout 17B** which has 500K TPD (5× the cap), 30K TPM
- Stopped bulk re-extraction; relied on existing 190 entities

**Lesson**: free tiers have daily ceilings. Calculate your token budget BEFORE committing to an overnight run. Use the higher-TPD models for bulk work.

### 9. Gemini embed quota = 1K RPD

**Symptom**: After re-embedding chunks during ECC reset, queries failed with `429: Quota exceeded for metric: embed_content_free_tier_requests, limit: 1000`.

**Root cause**: Free-tier Gemini embeddings cap at 1,000 requests/day. We burned it on bulk re-embedding 6,943 chunks (didn't realize they were already embedded from earlier sessions).

**Fix**: Got a fresh API key from a separate Google account. Avoided re-embedding by not resetting `epoch_processed` on chunks that already had embeddings.

**Lesson**: separate "rebuild" from "re-embed" — they're different operations with different costs. Check what's already done before redoing.

### 10. Upstream API response shape changed

**Symptom**: Pipeline 3 returned empty answers. The HTTPX call succeeded (200 OK), our parser read `natural_language_response` and got an empty string.

**Root cause**: Newer versions of the graphrag service (v1.3+) return `{response, retrieved, verbose}` instead of the older `{natural_language_response, query_sources}`. The service was doing the work — our parser was looking at the wrong keys.

**Fix**: Update `graph_rag.py:_parse_query_sources` to prefer the new keys (`response`, `verbose.selected_set`, `verbose.final_retrieval`), fall back to the old ones.

**Lesson**: SDK / API contracts shift between versions. Always log the raw response shape during integration — don't trust documentation that may be stale.

### 11. `similarity_threshold = 0.90` is too strict

**Symptom**: HybridRetriever returned 0 chunks for almost every query.

**Root cause**: 0.90 cosine sim is a very high bar. Gemini's 1536-d embeddings typically score 0.4–0.7 for relevant chunks; anything ≥ 0.85 is near-duplicate.

**Fix**: Drop to `0.50`. Catches reasonable matches without flooding the retriever with noise.

**Lesson**: defaults in open-source projects are often calibrated for one specific dataset/model. Always test thresholds on your own data before trusting them.

## Lessons that became architecture

These failures aren't just war stories. Each one became a defensible engineering decision:

| Failure | Architectural response |
|---|---|
| Provider rate-limits hit twice (#8, #9) | **`llm_client.py` abstraction** with provider/model env vars — flip with one config change |
| Token accounting was hidden (Pipeline 3's 13 score calls) | **`_read_token_usage_from_logs`** — honestly count all LLM calls per query |
| ECC unreliable (#5) | **`ecc_watchdog.py`** to auto-resume |
| Local file ingest failed (#6) | **`stream_documents` REST loader** in `ingest_graphrag.py` |
| Bad-prompt entities (#4, #7) | **`clean_bad_entities.py`** heuristic scrubber |
| 8B extraction garbage (#7) | Hybrid model strategy: smaller for build, bigger for queries |

The blog post should walk through *these decisions*, not just the failures. That's the engineering signal.

## Related

- [[06 - Pipeline 3 - GraphRAG]] — most failures live here
- [[03 - Zero Cost Stack]] — the rate-limit walls drove these choices
- [[13 - Defending The Project]] — turn failures into interview talking points
- [[14 - Honest Limitations]] — acknowledge what we DIDN'T solve

`#failures` `#learnings` `#engineering`
