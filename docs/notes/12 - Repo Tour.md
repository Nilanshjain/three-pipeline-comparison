# 12 - Repo Tour

> [!summary] One sentence
> Where every file lives and what it does. Open this when someone asks "where's the code for X?"

## Top-level layout

```
H:/tigergraph-hack/
├── backend/                    # FastAPI server + all pipelines
│   ├── app/
│   │   ├── api/                # HTTP endpoints
│   │   │   ├── benchmark.py    # /api/v1/benchmark/* — the heart of the project
│   │   │   ├── chat.py         # legacy chat endpoint (predates hackathon)
│   │   │   ├── metrics.py      # health / metrics
│   │   │   └── upload.py       # file upload (legacy)
│   │   ├── core/
│   │   │   ├── config.py       # Settings (env vars) — LLM_PROVIDER, LLM_MODEL, etc.
│   │   │   ├── database.py     # SQLAlchemy session
│   │   │   └── vector_storage.py  # Postgres JSON-array embedding storage
│   │   ├── services/
│   │   │   ├── llm_client.py   # ★ provider-agnostic LLM (Groq | Gemini)
│   │   │   ├── embeddings.py   # sentence-transformers (Pipeline 2)
│   │   │   ├── chunking.py     # text → chunks
│   │   │   ├── text_extraction.py # PDF / txt → text
│   │   │   ├── accuracy.py     # ★ LLM-as-Judge + BERTScore
│   │   │   └── pipelines/      # ★★ the three pipelines
│   │   │       ├── base.py     # Pipeline ABC + PipelineResult dataclass
│   │   │       ├── llm_only.py
│   │   │       ├── basic_rag.py
│   │   │       └── graph_rag.py   # most complex, most-tuned
│   │   └── main.py             # FastAPI app + routers
│   ├── tests/
│   │   ├── eval_questions.json      # ★ 10 curated benchmark questions
│   │   ├── accuracy_eval.py         # ★ runs eval over 10 questions
│   │   └── accuracy_results_*.json  # raw per-question JSON reports
│   ├── requirements.txt
│   ├── run.py
│   └── .env                    # secrets — gitignored
│
├── frontend/                   # React dashboard
│   ├── src/
│   │   ├── pages/Compare.jsx   # ★ the dashboard the judges will use
│   │   └── components/ui/      # Card, Button, Textarea, etc.
│   └── package.json
│
├── infra/
│   ├── graphrag-deploy/        # ★ Docker compose for the GraphRAG service
│   │   ├── docker-compose.yml
│   │   └── configs/
│   │       ├── server_config.example.json
│   │       └── server_config.json   # ★ has Savanna creds + LLM config (gitignored)
│   └── graphrag-upstream/      # git submodule of tigergraph/graphrag (read-only reference)
│
├── data/
│   ├── raw_articles/           # 432 Wikipedia AI/ML articles (.txt each)
│   ├── ingestion_temp/         # ECC scratch
│   └── *.txt logs              # fetch logs
│
├── scripts/
│   ├── fetch_dataset.py        # downloads the 432 Wiki articles
│   ├── ingest_basicrag.py      # → Postgres for Pipeline 2
│   ├── ingest_graphrag.py      # ★ → TigerGraph via runLoadingJobWithData
│   ├── ecc_watchdog.py         # ★ keep ECC alive overnight
│   ├── clean_bad_entities.py   # ★ scrub garbage entities from the graph
│   └── reset_processing_status.py  # forces ECC to re-process chunks
│
└── docs/
    ├── tuning_results.md       # ★ the C1/C2/C3 sweep
    └── notes/                  # ★ this Obsidian vault you're reading
        └── 00 - Index.md       # ← entry point
```

★ = files specifically built for this hackathon
★★ = the core deliverable

## What's where for each judging criterion

### Token Reduction (30%)
- `backend/app/services/pipelines/graph_rag.py:_read_token_usage_from_logs` — honest token counter
- `backend/app/api/benchmark.py:_summarize` — computes `token_reduction_vs_basic_pct`
- `docs/tuning_results.md` — the C1→C2→C3 reduction curve

### Answer Accuracy (30%)
- `backend/app/services/accuracy.py` — LLM-as-Judge + BERTScore
- `backend/tests/eval_questions.json` — 10 questions × 3 categories
- `backend/tests/accuracy_eval.py` — orchestrator
- `backend/tests/accuracy_results_C2.json` — best run we have

### Performance (20%)
- `backend/.env:LLM_MODEL = meta-llama/llama-4-scout-17b-16e-instruct` — Groq's fastest free model
- `backend/app/api/benchmark.py:asyncio.gather` — parallel pipeline execution

### Engineering & Storytelling (20%)
- `docs/notes/` — this vault
- `docs/tuning_results.md` — tuning experiment evidence
- `frontend/src/pages/Compare.jsx` — the dashboard with eval-question picker + reference cards
- `scripts/*` — the operational tooling we built

## Files judges will probably open

In rough priority order:
1. `README.md` — first impression
2. `docs/tuning_results.md` — the numbers
3. `backend/app/services/pipelines/graph_rag.py` — the heart of Pipeline 3
4. `frontend/src/pages/Compare.jsx` — the dashboard code
5. `backend/app/services/accuracy.py` — how we measured accuracy
6. `infra/graphrag-deploy/configs/server_config.example.json` — the GraphRAG service config (without secrets)

## Files NOT to mention unless asked

- `backend/.env` — has API keys
- `infra/graphrag-deploy/configs/server_config.json` — has Savanna apiToken
- `backend/tests/accuracy_results_*.json` — large blobs; the aggregate in `tuning_results.md` is more readable

## Helper commands cheat sheet

```bash
# Start everything (in order)
docker compose -f infra/graphrag-deploy/docker-compose.yml up -d
cd backend && ./venv/Scripts/python.exe -m uvicorn app.main:app --port 8765 &
cd frontend && npm start  # → opens http://localhost:3000

# Run the eval
cd backend && ./venv/Scripts/python.exe tests/accuracy_eval.py \
    --api http://localhost:8765/api/v1/benchmark/query \
    --skip-bertscore

# Ingest Pipeline 2 (Postgres)
python scripts/ingest_basicrag.py

# Ingest Pipeline 3 (TigerGraph)
python scripts/ingest_graphrag.py --limit 5  # smoke test
python scripts/ingest_graphrag.py            # full corpus

# When ECC stalls
python scripts/ecc_watchdog.py --interval 60
```

## Related

- [[00 - Index]] — navigation
- [[02 - Three Pipelines]] — how the pipeline files compose
- [[09 - Benchmark Harness]] — how the API ties them together

`#repo` `#filemap`
