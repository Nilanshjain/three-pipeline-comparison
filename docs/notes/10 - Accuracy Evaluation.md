# 10 - Accuracy Evaluation

> [!summary] One sentence
> Two metrics: LLM-as-Judge (pass/fail by a separate model) + BERTScore (semantic similarity to reference). Together they measure whether a pipeline's answer is actually *correct*, not just plausible.

Code: `backend/app/services/accuracy.py` + `backend/tests/accuracy_eval.py`.

## Why we need two metrics

A pipeline can produce text that's *fluent* and *on-topic* but factually wrong. We need a measurement that catches:
- ✅ "DeepMind was founded by Demis Hassabis, Shane Legg, Mustafa Suleyman in 2010 in London" (reference-aligned)
- ❌ "DeepMind was founded by Demis Hassabis, Tom Haveland, Shane Legg in 2010 in London" (fluent but wrong)

Both metrics try to detect that ❌ case:
- **LLM-as-Judge**: asks another LLM "is this prediction factually consistent with the reference?"
- **BERTScore**: measures word-level overlap weighted by importance

They have different failure modes — see "When each fails" below.

## The 10-question eval set

`backend/tests/eval_questions.json` — three categories:

| Category | Count | What it tests | Where each pipeline excels |
|---|---|---|---|
| `single_fact` | 4 | One fact lookup ("Who founded DeepMind?") | LLM-Only often wins if the fact is well-known |
| `multi_hop` | 4 | Joins facts across documents ("Which OpenAI co-founder was Hinton's student?") | GraphRAG should win — vectors can't reason |
| `synthesis` | 2 | Aggregate/compare ("How does GraphRAG differ from Basic RAG?") | GraphRAG or community summaries should win |

Why this split? It directly tests the **GraphRAG thesis**: multi-hop and synthesis are where graphs beat vectors. If our results don't show a GraphRAG advantage on multi-hop questions, the thesis is wrong for our corpus.

## LLM-as-Judge

### Setup

- **Judge model**: `meta-llama/Meta-Llama-3.1-8B-Instruct`
- **Provider**: HuggingFace Inference Providers (free tier)
- **Why a different model than the pipelines**: avoid self-judging bias. Our pipelines use Llama 4 Scout 17B (Groq); the judge is Llama 3.1 8B (HF). Different size, different family, different infra.

### Prompt

```
You are a strict factual evaluator. Compare a predicted answer to a reference answer.
Respond with exactly two lines:
Line 1: PASS or FAIL (uppercase, single word).
Line 2: A one-sentence reason.

Question: {question}
Reference: {reference}
Prediction: {prediction}

Verdict:
```

The judge returns `PASS` if the prediction is factually consistent + addresses the question; `FAIL` if it contradicts, omits a key fact, or is off-topic.

### Why this metric is imperfect

- The judge is a single LLM with its own quirks — it can be lenient or strict in inconsistent ways
- It can be fooled by fluent but wrong answers if the lie sounds confident
- 10 questions is too few for tight error bars — a single judge flip moves us 10pp

We compensate by **also using BERTScore** as a separate signal.

## BERTScore

### What it is

BERTScore embeds both prediction and reference using a BERT-family model, then computes a precision/recall/F1 over token-level cosine similarities. Unlike LLM-as-Judge, it's:
- Deterministic (same input → same output every time)
- Local (no API call)
- Fine-grained (continuous score, not binary)

### Two variants we report

1. **`f1_raw`**: typical BERTScore F1, range ~0.5–1.0 for English
2. **`f1_rescaled`**: same metric but rescaled against a baseline corpus (more interpretable), range ~0.0–1.0

Hackathon bonus thresholds:
- `f1_rescaled ≥ 0.55` OR `f1_raw ≥ 0.88` → bonus points
- Hitting both **AND** ≥90% judge pass rate → maximum bonus

### Why it's imperfect

- Measures *surface similarity*, not factual correctness — two correct answers worded differently get low scores
- Doesn't know what's salient — wrong but in-domain words can score high
- Doesn't differentiate true reasoning from plausible-sounding text

### Why we still report it

Because LLM-as-Judge and BERTScore have **uncorrelated failure modes**. A real win shows up in both. If the judge says PASS but BERTScore is low, that's a flag for "fluent but reworded answer." If BERTScore is high but the judge says FAIL, that's "near-copy of reference but missing a key fact."

## How accuracy_eval.py works

```python
for each question:
    result = POST /benchmark/query  # runs all 3 pipelines
    for each pipeline:
        grading = grade_one(
            question, reference, pipeline.answer,
            skip_judge=False, skip_bertscore=False
        )
        pipeline["grading"] = grading
    save partial results

summary = aggregate(per_question_results)
print_report(summary)
save final JSON
```

Reports aggregate per-pipeline:
- `judge_pass_rate`: fraction of PASSes
- `bertscore_f1_raw_mean`, `bertscore_f1_rescaled_mean`
- `mean_total_tokens`, `mean_latency_ms`, `mean_cost_usd`
- `n_errors`

## When each metric fails

| Scenario | Judge says | BERTScore | Notes |
|---|---|---|---|
| Pipeline returns the reference verbatim | PASS | very high | trivial perfect score |
| Pipeline returns correct fact in different words | PASS | medium | true win |
| Pipeline returns plausible but wrong fact (hallucination) | should say FAIL but sometimes lets through | medium | judge weak point |
| Pipeline says "I don't know" | FAIL | low | clear loss |
| Pipeline returns the question back as answer | should be FAIL | medium-high | BERTScore weakness — words overlap |
| Pipeline returns an over-long answer with the right fact buried | mostly PASS | medium | BERTScore penalized for verbose |

This is why **both metrics together** give a more honest picture than either alone.

## Our actual numbers

After the C2 tuning experiment ([[docs/tuning_results.md]]):

| Pipeline | judge_pass% | bertscore_f1_rescaled (TBD) | bertscore_f1_raw (TBD) |
|---|---|---|---|
| llm_only | 90% | — | — |
| basic_rag | 60% | — | — |
| graph_rag | 90% | — | — |

(We ran with `--skip-bertscore` to save time during tuning sweeps. Need a full eval pass with BERTScore enabled to fill those columns.)

## Defensive points for judges

- **"Your judge is just another LLM, isn't that circular?"** True. That's why we report BERTScore too. The hackathon spec mandates this metric, and we used the prescribed model (`Meta-Llama-3.1-8B-Instruct`).
- **"10 questions isn't statistically significant."** Correct — see [[14 - Honest Limitations]]. We frame results as "on this specific eval, ..." not "in general, ...". Round 2 would scale to 50–100M tokens with proportionally more questions.
- **"Why didn't you run BERTScore?"** We ran the full eval with it earlier; the tuning sweep skipped BERTScore for speed. A final run with both metrics is a 5-minute job.

## Related

- [[09 - Benchmark Harness]] — what gets evaluated
- [[02 - Three Pipelines]] — why fair comparison matters
- [[14 - Honest Limitations]] — caveats on small eval sets and judge bias

`#accuracy` `#evaluation` `#metrics`
