"""
Accuracy evaluation primitives.

Two metrics, matching the hackathon's required eval:

1. LLM-as-Judge — a free hosted Hugging Face Inference model grades each
   (question, prediction, reference) tuple PASS/FAIL.
2. BERTScore — semantic similarity of prediction vs reference. The
   hackathon awards bonus points for F1 rescaled >= 0.55 OR raw F1 >= 0.88.

Both functions operate on a single example. Aggregation lives in the
runner (backend/tests/accuracy_eval.py).
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Optional

from app.core.config import settings


logger = logging.getLogger(__name__)


# ---------- LLM-as-Judge ----------

JUDGE_MODEL = "meta-llama/Meta-Llama-3.1-8B-Instruct"

JUDGE_PROMPT = """You are a strict factual evaluator. Compare a predicted answer to a reference answer for a question.

Respond with exactly two lines:
Line 1: PASS or FAIL (uppercase, single word).
  - PASS = the prediction is factually consistent with the reference and addresses the question.
  - FAIL = the prediction contradicts the reference, omits the key fact, or is off-topic.
Line 2: A one-sentence reason.

Question: {question}
Reference: {reference}
Prediction: {prediction}

Verdict:"""


@dataclass
class JudgeResult:
    passed: bool
    reason: str
    raw: str
    error: Optional[str] = None


def llm_judge(
    question: str,
    prediction: str,
    reference: str,
    *,
    model: str = JUDGE_MODEL,
    hf_token: Optional[str] = None,
    max_new_tokens: int = 80,
) -> JudgeResult:
    """Grade a single (prediction, reference) pair via HF Inference API."""
    token = hf_token or settings.hf_token
    if not token:
        return JudgeResult(
            passed=False,
            reason="",
            raw="",
            error="HF_TOKEN not configured (set hf_token in .env)",
        )

    try:
        # Imported lazily so missing deps don't break unrelated code paths.
        from huggingface_hub import InferenceClient
    except ImportError as e:
        return JudgeResult(passed=False, reason="", raw="", error=f"huggingface_hub missing: {e}")

    if not prediction.strip():
        return JudgeResult(passed=False, reason="empty prediction", raw="")

    prompt = JUDGE_PROMPT.format(
        question=question.strip(),
        reference=reference.strip(),
        prediction=prediction.strip(),
    )

    try:
        client = InferenceClient(model=model, token=token, timeout=60)
        # HF Inference Providers (e.g. novita) now expect chat_completion, not
        # raw text_generation, for instruction-tuned models like Llama-3.1-8B-Instruct.
        #
        # Determinism note: the HF serverless backend (Novita/TGI) does NOT
        # honor `seed` reliably — we tested 5 identical calls on the borderline
        # Q12 case and got 3 FAIL / 2 PASS. So we don't rely on seed for
        # determinism. The real variance fix lives at the caller: see
        # `llm_judge_consensus` which votes N independent calls.
        #
        # We keep temperature=0 (low-sample) and pass `seed` opportunistically
        # in case the backend ever starts honoring it. Tested: temperature=0.0
        # works on Novita without errors.
        try:
            chat = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_new_tokens,
                temperature=0.0,
                seed=42,
            )
        except TypeError:
            # Older huggingface_hub doesn't accept seed= kwarg. Retry without it.
            chat = client.chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_new_tokens,
                temperature=0.0,
            )
        raw = chat.choices[0].message.content or ""
    except Exception as e:
        logger.exception("LLM judge call failed")
        return JudgeResult(passed=False, reason="", raw="", error=str(e))

    return _parse_verdict(raw)


def llm_judge_consensus(
    question: str,
    prediction: str,
    reference: str,
    *,
    n: int = 3,
    model: str = JUDGE_MODEL,
    hf_token: Optional[str] = None,
    max_new_tokens: int = 80,
) -> JudgeResult:
    """Run llm_judge N times and return the majority verdict.

    The HF Novita backend ignores the `seed` parameter — identical (pred, ref)
    pairs return different PASS/FAIL verdicts on borderline cases (we observed
    3 FAIL / 2 PASS over 5 calls on Q12's answer).

    Self-consistency (Wang et al 2022, arxiv 2203.11171) converts this
    variance into a stable signal: vote N independent judge calls and take
    the majority. With N=3, a borderline 50/50 case becomes deterministic
    in the limit (any 2 of 3 agree).

    Cost: 3x judge API calls per (pipeline, question) pair. At 14q x 3
    pipelines x 3 calls = 126 calls per eval, ~2 min total (well within HF
    free tier rate limits).
    """
    if n < 1:
        raise ValueError("n must be >= 1")
    if n == 1:
        return llm_judge(
            question, prediction, reference,
            model=model, hf_token=hf_token, max_new_tokens=max_new_tokens,
        )

    verdicts: list[bool] = []
    last_ok: Optional[JudgeResult] = None
    last_err: Optional[JudgeResult] = None
    for _ in range(n):
        r = llm_judge(
            question, prediction, reference,
            model=model, hf_token=hf_token, max_new_tokens=max_new_tokens,
        )
        if r.error:
            last_err = r
            continue
        verdicts.append(r.passed)
        last_ok = r

    if not verdicts:
        # All N calls errored — propagate the error
        return last_err or JudgeResult(
            passed=False, reason="", raw="", error="all consensus calls failed",
        )

    passed_count = sum(verdicts)
    majority = passed_count > len(verdicts) / 2
    # Keep one representative reason string for the report; prefix with vote tally
    return JudgeResult(
        passed=majority,
        reason=f"[consensus {passed_count}/{len(verdicts)} PASS] {last_ok.reason if last_ok else ''}",
        raw=last_ok.raw if last_ok else "",
        error=None,
    )


def _parse_verdict(raw: str) -> JudgeResult:
    lines = [l.strip() for l in raw.strip().splitlines() if l.strip()]
    if not lines:
        return JudgeResult(passed=False, reason="", raw=raw, error="empty model output")

    verdict = lines[0].upper()
    # Tolerate the model emitting "Verdict: PASS" or similar prefixes.
    m = re.search(r"\b(PASS|FAIL)\b", verdict)
    passed = m.group(1) == "PASS" if m else False
    reason = lines[1] if len(lines) > 1 else ""
    return JudgeResult(passed=passed, reason=reason, raw=raw)


# ---------- BERTScore ----------

@dataclass
class BertScoreResult:
    f1_raw: float
    f1_rescaled: float
    error: Optional[str] = None


def bertscore_metrics(
    prediction: str,
    reference: str,
    *,
    lang: str = "en",
) -> BertScoreResult:
    """Compute raw + baseline-rescaled BERTScore F1 for one example.

    Both numbers reported because the hackathon bonus thresholds are
    expressed for both variants (>= 0.55 rescaled, >= 0.88 raw).
    """
    if not prediction.strip() or not reference.strip():
        return BertScoreResult(f1_raw=0.0, f1_rescaled=0.0, error="empty input")

    try:
        from bert_score import score as _score
    except ImportError as e:
        return BertScoreResult(f1_raw=0.0, f1_rescaled=0.0, error=f"bert_score missing: {e}")

    try:
        # bert_score loads a fairly large model on first call (cached afterwards).
        _, _, f1_raw = _score([prediction], [reference], lang=lang, rescale_with_baseline=False)
        _, _, f1_rescaled = _score([prediction], [reference], lang=lang, rescale_with_baseline=True)
        return BertScoreResult(
            f1_raw=float(f1_raw[0].item()),
            f1_rescaled=float(f1_rescaled[0].item()),
        )
    except Exception as e:
        logger.exception("BERTScore failed")
        return BertScoreResult(f1_raw=0.0, f1_rescaled=0.0, error=str(e))
