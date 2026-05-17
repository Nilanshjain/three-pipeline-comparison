# 04 - Pipeline 1 - LLM Only

> [!summary] One sentence
> Ask the LLM the question directly with zero retrieval — answer comes from its training data alone.

## What it does

```
Question → Groq Llama 3.3 70B → Answer
```

That's it. No database, no vector search, no graph. The model relies on what it learned during pre-training (its **parametric knowledge**).

Code: `backend/app/services/pipelines/llm_only.py` — ~20 lines.

## Why include this pipeline at all?

Three reasons:

1. **Baseline cost.** Shows what one bare LLM call looks like in tokens, latency, and dollars. Other pipelines can be compared against it.
2. **Sanity check for eval questions.** If LLM-Only nails a question, the LLM already knew it — that question doesn't test retrieval. Useful for identifying which eval questions are actually challenging.
3. **Honest comparison.** Sometimes retrieval is overkill. Pulling 3 KB of context to answer "What's 2+2?" wastes tokens. The dashboard reveals when LLM-Only is the right tool.

## Code walkthrough

```python
class LLMOnlyPipeline(Pipeline):
    name = "llm_only"

    async def run(self, query: str, **_) -> PipelineResult:
        start = time.perf_counter()
        result = await complete(query)         # one LLM call
        latency_ms = (time.perf_counter() - start) * 1000

        return PipelineResult(
            pipeline=self.name,
            answer=result.text,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            latency_ms=latency_ms,
            cost_usd=cost_usd(...),
            retrieved_chunks=[],   # always empty
            model=result.model,
        )
```

`complete()` is in `backend/app/services/llm_client.py` — the abstraction layer over Groq/Gemini. See [[03 - Zero Cost Stack]].

## Expected behavior

Tested empirically — Llama 3.3 70B's parametric knowledge:

| Question | What happens | Why |
|---|---|---|
| "What is RAG?" | Says "Raise and Give" (university fundraiser) ❌ | Common acronym ambiguity — model picks the wrong meaning |
| "Who founded DeepMind?" | Correct: Hassabis, Legg, Suleyman, 2010, London ✅ | High-profile public knowledge in training data |
| "Which of the 2018 Turing Award co-recipients have worked at Google?" | Correct on names, less precise on dates | Multi-hop but well-known |
| Domain-specific questions on private docs | Hallucinates or refuses | Not in training data |

This is why retrieval matters — for **specific, domain, or recent** information, the LLM doesn't know.

## Metrics this pipeline produces

A representative run for "Who founded DeepMind?":

| Metric | Value | Interpretation |
|---|---|---|
| `prompt_tokens` | 14 | Just the question wrapped in chat format |
| `completion_tokens` | 65 | The answer text |
| `total_tokens` | 79 | The full LLM bill |
| `latency_ms` | ~300 | Single Groq LPU call |
| `cost_usd` | $0 | Groq free tier |
| `retrieved_chunks` | [] | None |

These numbers are the **floor** — no pipeline can be cheaper than LLM-Only on a single-shot answer.

## Things to anticipate from questioners

> *"This is trivial. Why is it part of a 'pipeline' framework?"*

Because uniformity makes the benchmark fair. By implementing the same interface (`Pipeline.run() → PipelineResult`), the benchmark harness can `asyncio.gather()` all three without special-casing.

> *"How do you know LLM-Only is 'wrong' vs 'right'?"*

The accuracy eval ([[10 - Accuracy Evaluation]]) uses LLM-as-Judge with a reference answer. For multi-hop or synthesis questions, LLM-Only often hallucinates plausible-but-wrong details — the judge catches this.

> *"What if you used a bigger model like GPT-4? Wouldn't LLM-Only win everything?"*

For *general* knowledge, possibly. But:
- GPT-4 isn't free
- The hackathon's premise is *private* / specialized data
- We use the same model in all three pipelines, so Pipeline 2 and 3 also benefit from a stronger base

## Related

- [[02 - Three Pipelines]] — where this fits in the overall architecture
- [[03 - Zero Cost Stack]] — what `complete()` actually calls
- [[05 - Pipeline 2 - Basic RAG]] — the next step up
- [[09 - Benchmark Harness]] — how all three pipelines run in parallel

`#pipeline-1` `#baseline`
