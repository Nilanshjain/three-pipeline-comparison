# Demo Video Script (~6 min)
# Three Pipelines. Same Model. Every Token Counted.

Target: **5-7 minutes** (hackathon spec). Aim for **6 min** total.

Tools: **OBS Studio** (free) or **Loom** (hosted). 1080p, 30fps. Capture full browser + system audio.

---

## Pre-record checklist

- [ ] Backend up on `http://localhost:8765` — `curl http://localhost:8765/api/v1/benchmark/eval-questions` returns JSON
- [ ] Savanna workspace **Running** at tgcloud.io
- [ ] Docker containers up: `docker ps` shows `devrag-graphrag`, `devrag-graphrag-ecc`, `devrag-chat-history`
- [ ] React dev server: `cd frontend && npm start` → `http://localhost:3000`
- [ ] Close all other tabs / Slack / notifications
- [ ] Open `accuracy_results_C26_FINAL.json` in a pre-formatted browser tab (one for fallback if the live API stutters)
- [ ] Have the GitHub repo URL on a sticky note
- [ ] Record one practice take first — most takes need a re-do

---

## Scene 1 — The hook (0:00–0:30)

**Screen**: Dashboard at `http://localhost:3000` showing the curated-question panel + empty results area.

**Say**:

> *"I built three RAG pipelines side-by-side — LLM-Only, Basic RAG, and GraphRAG — on the same corpus, with the same synthesis model, and I counted every single LLM call honestly. Two wins came out of it: −42.8% tokens vs Basic RAG for the headline rubric, and the maximum bonus tier — judge ≥90% AND F1_raw ≥0.88 in a single run — unlocked. I'm Nilansh, this is my TigerGraph GraphRAG Hackathon submission."*

**Key visual**: hover over the 14 curated questions panel; don't click yet.

---

## Scene 2 — Architecture in 60 seconds (0:30–1:30)

**Screen**: Open `docs/architecture.md` "System overview" Mermaid diagram in a side tab.

**Say**:

> *"Quick architecture. FastAPI backend runs all three pipelines in parallel via asyncio. Pipeline 1 is the LLM with no retrieval. Pipeline 2 is Basic RAG — embed, search Postgres, send chunks to LLM. Pipeline 3 is GraphRAG against TigerGraph Savanna — community summaries, entity graph, the works.*
>
> *Fairness rule: same Llama 4 Scout 17B on Groq across all three pipelines. The token delta reflects retrieval strategy, not model choice. And the GraphRAG pipeline has an adaptive fallback — if the cheap community-summary retrieval returns a refusal phrase, we fire a 2-hop graph-traversal retry to surface the missing entity chunks."*

**Key visual**: highlight that all three pipelines arrow to the same "Groq Llama 4 Scout 17B" node. Then scroll to the "C26 max-bonus path" diagram to show the fallback flow.

---

## Scene 3 — Live dashboard demo, headline rubric (1:30–3:00)

**Screen**: Back to the dashboard. Click **Q1: "Who founded DeepMind, and in what year and city?"** (single-fact, where C11 default shines).

**Say while results load**:

> *"Single-fact question — exactly where the C11 default should win cleanly. Watch the token counts."*

**Wait for results, walk through**:

> *"Three answers. LLM-Only knew it from training. Basic RAG retrieved 5 chunks, ~1,400 tokens. GraphRAG — community-summary mode — 783 tokens, one LLM call. Same correct answer, half the tokens. That green badge says '1 LLM call' — that's the combine=True setting that bypasses the upstream score_candidate re-ranker."*

**Key visuals**:
- Point at the per-card LLM-call badge
- Open "Retrieved context" on the GraphRAG card to show the community summary text
- Compare with Basic RAG's 5 chunks side-by-side

**Click Q6: "Which OpenAI co-founder was previously a PhD student of Geoffrey Hinton?"** (multi-hop, where adaptive fallback unlocks the answer):

> *"This is the multi-hop case. The community summary doesn't surface the Sutskever-Hinton PhD link. Vector retrieval embeds toward 'OpenAI' chunks. Without help, the answer hedges. Watch the GraphRAG card — it shows 3 internal LLM calls instead of 1. The adaptive fallback fired: a 2-hop graph traversal followed the OpenAI → Sutskever → Hinton entity edges and surfaced the right chunk. Reference answer at the top — judge can verify."*

**Key visual**: the LLM-call badge changing from 1 (Q1) to 3 (Q6) — visible proof the adaptive fallback fired.

---

## Scene 4 — The two wins, side by side (3:00–4:30)

**Screen**: Switch to `docs/tuning_results.md` — the "Bonus tier landscape (final)" table.

**Say**:

> *"Two distinct wins from one codebase. C11 is the default config — 805 tokens per query versus Basic RAG's 1,407, that's −42.8% tokens, AND +7.1 percentage points higher judge accuracy. The hackathon headline metric is satisfied: token reduction WITH maintained accuracy.*
>
> *Then C26 — opt-in via one flag — stacks three engineering pieces: a 2-hop graph-traversal fallback for multi-hop entities, a trim_answer post-processor that strips upstream LLM markdown, and judge self-consistency N=3 voting that compensates for HuggingFace Inference's per-call variance. Result: judge 92.9% AND F1_raw 0.891 in the SAME eval run. Maximum bonus tier unlocked. Both numbers reproducible from `accuracy_results_C26_FINAL.json` in the repo."*

**Key visual**: the bonus tier table — both ✅ checkmarks on the C26 row. Hold for 2 seconds.

**Say**:

> *"Most submissions will pick one rubric. We deliver both as configurable trade-offs on the same pipeline. Token-conscious users get C11. Accuracy-first users flip the adaptive_fallback flag for C26."*

---

## Scene 5 — Honest measurement + Q12 (4:30–5:15)

**Screen**: Stay on `tuning_results.md`. Scroll to the "Five engineering findings" section.

**Say**:

> *"Three things to flag for credibility. First: I count every internal LLM call by scraping docker container logs after each query. The default GraphRAG config makes 14 LLM calls per query — 13 score_candidate re-rankers plus synthesis. Most teams report only synthesis tokens; that hides 13× the real cost. The −42.8% claim only matters because it's the HONEST total.*
>
> *Second: the C26 config uses ~1.8× MORE tokens than Basic RAG, not fewer. It wins the accuracy bonus, not the token rubric. Both wins are real, neither is exaggerated.*
>
> *Third: Q12 — the LSTM versus RNN question — still fails. The community summary returns 'RNN' confidently, no refusal phrase catches it. 13 of 14 = 92.9% still clears the bonus floor, but I'm calling out the one open problem instead of hiding it. Chain-of-Verification would be the next step."*

**Key visuals**: the "Five engineering findings" callouts; pause on each numbered finding for 2 seconds.

---

## Scene 6 — Close (5:15–6:00)

**Screen**: Back to the dashboard. Show the eval-questions panel with the C26 numbers visible somewhere on the page (or stay on tuning_results.md).

**Say**:

> *"Repo: github.com/Nilanshjain/DevRAG. Blog post at docs/blog_post.md walks the full 26-config tuning frontier. Architecture diagrams in docs/architecture.md. 15-note Obsidian vault in docs/notes/ documents every architectural decision and every failure mode I hit.*
>
> *Headline rubric satisfied. Maximum bonus tier unlocked. Engineering decisions documented and reproducible. Thanks for watching."*

---

## Editing notes

- **Cut tight** — every 'um' and pause should get cut. Talking density matters.
- **Background music**: optional, very low volume, instrumental (lofi works). Not required.
- **Captions / subtitles**: highly recommended, auto-generate then proofread the technical terms.
- **Title card** at the start (5s):
  > **Three Pipelines. Same Model. Every Token Counted.**
  > *A side-by-side RAG benchmark — TigerGraph GraphRAG Hackathon submission by Nilansh Jain*
- **End card** (5s) with the GitHub link visible.
- **Compress for upload**: target ~50-100MB at 1080p30 for unlisted YouTube; H.264 codec.

## Practice before recording

1. **Pronounce "Llama 4 Scout 17B"** — "ell-AH-ma four scout seventeen B"
2. **The numbers from memory**: −42.8% tokens (C11), 92.9% judge + 0.891 F1_raw (C26), 13/14 pass
3. **Don't say "honestly" too many times** — pick one moment per scene
4. **Where to click in the dashboard** — walk through the Q1 → Q6 flow once before recording
5. **The LLM-call badge** — confirm it changes from 1 (Q1) to 3 (Q6) — that's the visible proof of adaptive fallback

## Backup plan if something breaks live

- **Savanna suspended**: have a screen recording of a prior successful Q1/Q6 run pre-staged. Cut to that.
- **Pipeline 3 errors**: skip the multi-hop demo, just show Q1 + the tuning_results table.
- **Backend dies**: restart it before continuing — expected during live demos.

## Length budget

| Scene | Target | Cumulative |
|---|---|---|
| Hook | 0:30 | 0:30 |
| Architecture | 1:00 | 1:30 |
| Live demo (Q1 + Q6) | 1:30 | 3:00 |
| Two wins side by side | 1:30 | 4:30 |
| Honest measurement + Q12 | 0:45 | 5:15 |
| Close | 0:45 | 6:00 |

If over 6:30, trim "Two wins side by side" to 1:00 by cutting the second paragraph.

## After upload

- Upload to **YouTube unlisted** (hackathon usually accepts this)
- Title: `Three Pipelines. Same Model. Every Token Counted. — Max Bonus Tier Unlocked | TigerGraph GraphRAG Hackathon`
- Description: GitHub link + 1-paragraph TL;DR with both win headlines
- Add timestamps:
  ```
  0:00 The two wins
  0:30 Architecture
  1:30 Live demo (single-fact + multi-hop)
  3:00 Headline rubric + max bonus side by side
  4:30 Honest measurement + Q12 limitations
  5:15 Wrap-up
  ```
- Paste the YouTube link into the Unstop submission form
