# C11 Baseline Restore Instructions

This snapshot is the known-good state with C11 as Pipeline 3 default.

**Working numbers (do NOT lose):**
- GraphRAG (C11) on 14q: judge 71.4%, F1_raw 0.863, F1_resc 0.190, tokens 805
- Token reduction: -42.8% vs Basic RAG (1407)
- Accuracy: +7.1pp over Basic RAG (64.3%)
- Hackathon headline rubric SATISFIED

## To restore if any experiment breaks something:

```bash
SNAP="snapshots/c11_baseline_<TIMESTAMP>"
cp $SNAP/graph_rag.py backend/app/services/pipelines/graph_rag.py
cp $SNAP/server_config.json infra/graphrag-deploy/configs/server_config.json
cp $SNAP/eval_questions.json backend/tests/eval_questions.json
# Result JSONs are read-only, restore only if needed
```

Then:
- Restart backend: `cd backend && python -m uvicorn app.main:app --port 8765`
- Restart graphrag if config changed: `docker compose -f infra/graphrag-deploy/docker-compose.yml restart graphrag`
- Verify: `curl -X POST http://localhost:8765/api/v1/benchmark/query -d '{"query":"Who founded DeepMind?","pipelines":["graph_rag"]}'`
- Should return ~775 tokens, "Hassabis, Legg, Suleyman" answer.

## Also delete the per-graph prompt override if any experiment created one:

```bash
rm -f infra/graphrag-deploy/configs/graph_configs/Nilanshgraph/prompts/chatbot_response.txt
```
