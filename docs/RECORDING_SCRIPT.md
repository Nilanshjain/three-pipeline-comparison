# Demo Recording Script — read along while recording

**Total length: ~6 minutes.** Speak at a natural pace — about 140 words per minute. Keep this open on your second monitor or printed.

**Legend:**
- `[ACTION: ... ]` = what you do on screen
- `[PAUSE]` = brief silence, let the screen catch up
- Regular text = what you say out loud

**Pre-flight before hitting record:**
1. Three browser tabs open:
   - **Tab 1**: `http://localhost:3000` — the dashboard
   - **Tab 2**: `file:///H:/tigergraph-hack/docs/html/index.html` — README rendered
   - **Tab 3**: `file:///H:/tigergraph-hack/docs/html/architecture.html` — architecture diagrams
2. Tab 1 (dashboard) is the active one
3. Toggle is OFF (green, says "Default (token-reduction path)")
4. No previous query results showing — fresh page
5. Close Slack, notifications, other apps
6. Mic level checked, room quiet

---

## SCENE 1 — Hook (0:00 – 0:30)

`[ACTION: Tab 1 dashboard visible. Sit on the landing page for 2 seconds before talking.]`

Hi, I'm Nilansh. This is my submission for the TigerGraph GraphRAG Inference Hackathon.

I built three retrieval pipelines side by side — a plain LLM, a Basic RAG with vector search, and a GraphRAG running against TigerGraph Savanna. All three use the same synthesis model so the comparison is fair, and every single LLM call is honestly counted — including the ones the upstream GraphRAG service makes internally for re-ranking.

`[ACTION: Hover over the page header so the title is visible on screen.]`

Two things came out of this. A token reduction win on the headline rubric, and the maximum bonus tier unlocked in a single eval run. Let me show you both.

---

## SCENE 2 — The two wins, upfront (0:30 – 1:45)

`[ACTION: Scroll down slightly to reveal the "Saved benchmark runs" card. Click on it to expand.]`

`[PAUSE — wait for the panel to expand showing both tables.]`

Before any live demo, here's the proof. These are the full 14-question aggregate scores from saved JSON files in the repo.

`[ACTION: Point cursor at the first row, "Default config".]`

The Default config — that's the regular Pipeline 3 setting. GraphRAG uses 805 tokens per question. Basic RAG uses 1,407. That's negative 42.8% tokens. And the judge accuracy is 71.4% — seven points higher than Basic RAG. That satisfies the hackathon's headline rubric: token reduction with maintained or improved accuracy.

`[ACTION: Point cursor at the second row, "Adaptive config — Maximum Bonus Tier".]`

Now the second row. The Adaptive config — opt-in by flipping one flag. This one was built specifically to chase the bonus tier. Judge accuracy hits 92.9 percent. BERTScore F1_raw hits 0.891. The hackathon's bonus rule requires both judge above 90 AND F1 above 0.88, in the same run. Both green checkmarks here.

Two configurations. Two rubrics. Same codebase. The adaptive config trades roughly 3x the tokens for the accuracy needed to clear the bonus thresholds — that's the design choice, not an accident.

`[ACTION: Click the Saved Results header again to collapse the panel. Cleaner view.]`

Let me show you the architecture, then we'll see it run live.

---

## SCENE 3 — Architecture in 60 seconds (1:45 – 2:45)

`[ACTION: Switch to Tab 3 (architecture.html). Scroll to the top "System overview" mermaid diagram.]`

Quick architecture. FastAPI backend on port 8765. When you submit a query, all three pipelines run in parallel using asyncio.

`[ACTION: Trace the three arrows from the Backend node with your cursor.]`

Pipeline 1 — LLM-Only — just sends the question straight to Groq's Llama 4 Scout 17B. One LLM call.

Pipeline 2 — Basic RAG — embeds the query with sentence-transformers, finds the top 5 similar chunks from Postgres, sends those chunks plus the question to Groq.

Pipeline 3 — GraphRAG — hits a Docker-hosted GraphRAG service that talks to TigerGraph Savanna. The graph has documents, chunks, entities, communities — the full knowledge graph schema.

`[ACTION: Highlight the three pipelines all pointing at "Groq Llama 4 Scout 17B".]`

The critical fairness rule: all three pipelines synthesize answers with the same Llama model. The token differences you'll see in a second reflect retrieval strategy, not model choice.

`[ACTION: Scroll down to the second diagram — "Pipeline 3 — C26 max-bonus path".]`

And this is the adaptive flow specifically. If the cheap primary call returns a refusal phrase like "couldn't find", the wrapper fires a second retrieval — this time walking two hops along entity edges to surface the chunks that vector match alone misses. The judge consensus voting on the right is what stabilizes our LLM-as-judge output.

---

## SCENE 4 — Live demo, single-fact question (2:45 – 3:45)

`[ACTION: Switch back to Tab 1 (dashboard). Confirm toggle is still OFF.]`

OK, let's run something live. I'll click Question 1.

`[ACTION: Scroll to "Curated eval set" panel. Click question #1 — "Who founded DeepMind, and in what year and city?"]`

`[PAUSE — wait for the three pipeline cards to render. Around 8 seconds.]`

Three answers come back simultaneously.

`[ACTION: Point at the LLM-Only card.]`

LLM-Only — 91 tokens. The model just knew it from training.

`[ACTION: Point at the Basic RAG card.]`

Basic RAG — about 1,600 tokens. Five chunks retrieved from Postgres, answer is correct.

`[ACTION: Point at the GraphRAG card. Highlight the "1 LLM call" badge in the corner.]`

GraphRAG — only 720 tokens. One LLM call. That's the default config — hierarchical retrieval, community summary plus one anchoring chunk. Same correct answer.

`[ACTION: Scroll up to the green "Token reduction vs Basic RAG" badge in the summary strip.]`

Notice the summary strip shows GraphRAG using over 50% fewer tokens than Basic RAG on this one question. That's the headline rubric in action.

`[ACTION: Click the "Retrieved context" expander on the GraphRAG card. Show the chunk/community text briefly.]`

If you want to see what was retrieved, every pipeline shows it. This builds judge trust — no black boxes.

`[ACTION: Collapse the retrieved context.]`

That's the easy case. Now let me show you a multi-hop question where the cheap config struggles and the adaptive path saves us.

---

## SCENE 5 — The adaptive toggle in action (3:45 – 5:00)

`[ACTION: Click question #6 — "Which OpenAI co-founder was previously a PhD student of Geoffrey Hinton?"]`

`[PAUSE — wait for results, around 10 seconds.]`

Question 6 — multi-hop. To answer, you need to know who OpenAI's co-founders are AND who Hinton's PhD students were, and find the overlap.

`[ACTION: Point at the GraphRAG card, specifically the "1 LLM call" badge.]`

GraphRAG with the default config — one LLM call. Look at the answer.

`[ACTION: Read or highlight the answer text on the GraphRAG card. It will say something like "Ilya Sutskever... However, based on the provided contexts, there is no direct information to confirm this."]`

It mentions Sutskever — from the LLM's parametric memory — but the retrieval didn't surface the supporting chunk. So it hedges. "No direct information to confirm this." That's a fail under a strict judge.

`[ACTION: Now flip the "Pipeline 3 mode" toggle to ON. The slider turns amber. The label changes to "Adaptive (max-bonus path)".]`

So I flip the adaptive toggle on. Now Pipeline 3 will watch for refusal phrases and retry with two-hop graph traversal if it detects one.

`[ACTION: Click question #6 again — same question, toggle now ON.]`

`[PAUSE — this one takes longer, around 15-20 seconds because the fallback fires.]`

`[ACTION: When results land, point at the GraphRAG card LLM-call badge. It should now say "3 LLM calls" or "4 LLM calls" — emphasize this with the cursor.]`

Same question, but now look at the call count. Three or four LLM calls instead of one. The graph traversal fallback fired.

`[ACTION: Read the answer on the GraphRAG card.]`

And the answer is now direct: "Ilya Sutskever, a co-founder of OpenAI, was previously a PhD student of Geoffrey Hinton at the University of Toronto."

That's the visible proof. The cheap path can't bridge the OpenAI–Sutskever–Hinton entity chain through vector embeddings alone. The graph walk does. Same codebase, one flag, two trade-offs.

---

## SCENE 6 — Honest measurement and limitations (5:00 – 5:30)

`[ACTION: Switch to Tab 2 (README rendered). Scroll to the "Five engineering findings" section.]`

Three things to flag for credibility.

First — I count every internal LLM call by scraping the GraphRAG Docker container's logs after every query. The default GraphRAG config actually fires 14 LLM calls per query: 13 internal `score_candidate` re-rankers plus one synthesis. Most submissions will report only the synthesis prompt and under-report cost by 13 times. The -42.8% token claim only matters because it's the honest total.

Second — the adaptive config uses about 2,500 tokens. That's more than Basic RAG, not fewer. It wins the accuracy bonus, not the token rubric. Two different configs for two different rubrics. We deliver both rather than pretend one config does it all.

Third — Question 12 still fails. The LSTM versus RNN one. The community summary confidently returns "RNN" instead of "LSTM" — no refusal phrase, so the fallback doesn't fire. 13 of 14 still clears the 90% bonus threshold, but I'm calling it out openly instead of hiding it.

---

## SCENE 7 — Close (5:30 – 6:00)

`[ACTION: Switch back to Tab 1 (dashboard).]`

That's the project. Two wins from one codebase. The README has the full methodology and the 26-configuration tuning frontier. Architecture diagrams, blog post, and the saved eval JSONs are all in the repo.

`[ACTION: Stay on the dashboard for the final 3 seconds. Maybe scroll back to the top so the title is visible.]`

Repo is at github dot com slash Nilanshjain slash DevRAG. Thanks for watching.

`[ACTION: Stop recording.]`

---

## Post-recording reminders

- **Trim the start and end** — cut any "OK I'm recording" or dead air
- **Cut all "ums"** — most takes need this
- **Add captions** — auto-generate with YouTube, then proofread the technical terms ("LLama 4 Scout 17B", "BERTScore", "Hochreiter")
- **Title for YouTube**: `Token Comparison Across Three RAG Pipelines — Max Bonus Tier Unlocked | TigerGraph GraphRAG Hackathon`
- **Description**: include GitHub link + timestamps
- **Timestamps**:
  - 0:00 The two wins
  - 0:30 Saved benchmark results
  - 1:45 Architecture
  - 2:45 Live demo — single-fact (Q1)
  - 3:45 Live demo — multi-hop with adaptive toggle (Q6)
  - 5:00 Honest measurement + Q12 limitation
  - 5:30 Wrap

## If something breaks during recording

| What breaks | What to do |
|---|---|
| Savanna 500s on a query | Don't panic. Open the Saved Results panel and narrate from there — same numbers, no Savanna needed. Mention briefly "live retrieval is sometimes slow against the cloud, but the saved JSONs are reproducible." |
| Q6 adaptive gives a weak answer | "Multi-hop answers vary slightly run-to-run — let me click again." Re-click. If still weak, narrate the saved C26 row. |
| Frontend tab dies | Refresh `localhost:3000`. The state resets but everything still works. |
| You stumble mid-sentence | Pause for 2 seconds, restart the sentence cleanly. Easy to edit out the bad take. |

## Words to pronounce correctly

- **Llama 4 Scout 17B** — "LAH-ma four scout seventeen B"
- **TigerGraph Savanna** — say each word separately
- **BERTScore** — "bert score"
- **Hochreiter / Schmidhuber** — "HOKE-rye-ter, SHMEED-hoo-ber"
- **Hassabis** — "HASS-a-biss" (Demis Hassabis)
- **Sutskever** — "SOOTS-kev-er"
- **Fei-Fei Li** — "FAY fay LEE"

Good luck. You've got this.
