"""
Accuracy eval runner.

Loops eval_questions.json through the live /benchmark/query endpoint,
grades every (pipeline, answer) pair via LLM-as-Judge + BERTScore, and
prints/saves an aggregated report.

Prereqs:
  - Backend running:   uvicorn app.main:app --reload --port 8000
  - Dataset ingested:  Pipelines 2 and 3 should have the AI/ML corpus
  - .env has:          GEMINI_API_KEY, HF_TOKEN, (TG_API_* once Pipeline 3 is wired)

Usage:
  python backend/tests/accuracy_eval.py
  python backend/tests/accuracy_eval.py --pipelines llm_only basic_rag
  python backend/tests/accuracy_eval.py --questions custom_questions.json
  python backend/tests/accuracy_eval.py --skip-bertscore   # faster iteration
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Any

# Allow running as `python backend/tests/accuracy_eval.py` from repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv

from app.services.accuracy import bertscore_metrics, llm_judge, llm_judge_consensus

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("accuracy_eval")


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_QUESTIONS = Path(__file__).resolve().parent / "eval_questions.json"
RESULTS_DIR = Path(__file__).resolve().parent
DEFAULT_API = "http://localhost:8000/api/v1/benchmark/query"


def run_pipelines(
    api: str,
    query: str,
    pipelines: list[str] | None,
    graphrag_config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    payload: dict[str, Any] = {"query": query}
    if pipelines:
        payload["pipelines"] = pipelines
    if graphrag_config:
        payload["graphrag_config"] = graphrag_config
    with httpx.Client(timeout=120.0) as client:
        r = client.post(api, json=payload)
        r.raise_for_status()
    return r.json()["pipelines"]


def grade_one(
    question: str,
    reference: str,
    prediction: str,
    *,
    skip_judge: bool,
    skip_bertscore: bool,
    judge_consensus_n: int = 1,
) -> dict[str, Any]:
    out: dict[str, Any] = {}
    if not skip_judge:
        if judge_consensus_n > 1:
            j = llm_judge_consensus(question, prediction, reference, n=judge_consensus_n)
        else:
            j = llm_judge(question, prediction, reference)
        out["judge_pass"] = j.passed
        out["judge_reason"] = j.reason
        if j.error:
            out["judge_error"] = j.error
    if not skip_bertscore:
        b = bertscore_metrics(prediction, reference)
        out["bertscore_f1_raw"] = round(b.f1_raw, 4)
        out["bertscore_f1_rescaled"] = round(b.f1_rescaled, 4)
        if b.error:
            out["bertscore_error"] = b.error
    return out


def aggregate(per_question: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Per-pipeline aggregate metrics across all graded questions."""
    by_pipeline: dict[str, dict[str, list[Any]]] = {}
    for row in per_question:
        for pipe in row["pipelines"]:
            name = pipe["pipeline"]
            slot = by_pipeline.setdefault(name, {
                "judge_passes": [],
                "f1_raw": [],
                "f1_rescaled": [],
                "tokens": [],
                "latency_ms": [],
                "cost_usd": [],
                "errors": 0,
            })
            if pipe.get("error"):
                slot["errors"] += 1
                continue
            slot["tokens"].append(pipe["total_tokens"])
            slot["latency_ms"].append(pipe["latency_ms"])
            slot["cost_usd"].append(pipe["cost_usd"])
            grading = pipe.get("grading", {})
            if "judge_pass" in grading:
                slot["judge_passes"].append(bool(grading["judge_pass"]))
            if "bertscore_f1_raw" in grading:
                slot["f1_raw"].append(grading["bertscore_f1_raw"])
                slot["f1_rescaled"].append(grading["bertscore_f1_rescaled"])

    summary: dict[str, dict[str, Any]] = {}
    for name, s in by_pipeline.items():
        n_graded_judge = len(s["judge_passes"])
        n_graded_bert = len(s["f1_raw"])
        summary[name] = {
            "n_questions": len(s["tokens"]) + s["errors"],
            "n_errors": s["errors"],
            "judge_pass_rate": (sum(s["judge_passes"]) / n_graded_judge) if n_graded_judge else None,
            "judge_n": n_graded_judge,
            "bertscore_f1_raw_mean": (sum(s["f1_raw"]) / n_graded_bert) if n_graded_bert else None,
            "bertscore_f1_rescaled_mean": (sum(s["f1_rescaled"]) / n_graded_bert) if n_graded_bert else None,
            "mean_total_tokens": (sum(s["tokens"]) / len(s["tokens"])) if s["tokens"] else None,
            "mean_latency_ms": (sum(s["latency_ms"]) / len(s["latency_ms"])) if s["latency_ms"] else None,
            "mean_cost_usd": (sum(s["cost_usd"]) / len(s["cost_usd"])) if s["cost_usd"] else None,
        }
    return summary


def print_report(summary: dict[str, dict[str, Any]]) -> None:
    headers = [
        "pipeline", "judge_pass%", "F1_resc", "F1_raw",
        "tokens", "latency_ms", "cost_usd", "errors",
    ]
    rows = []
    for name, s in summary.items():
        rows.append([
            name,
            f"{s['judge_pass_rate']*100:.1f}" if s['judge_pass_rate'] is not None else "—",
            f"{s['bertscore_f1_rescaled_mean']:.3f}" if s['bertscore_f1_rescaled_mean'] is not None else "—",
            f"{s['bertscore_f1_raw_mean']:.3f}" if s['bertscore_f1_raw_mean'] is not None else "—",
            f"{s['mean_total_tokens']:.0f}" if s['mean_total_tokens'] is not None else "—",
            f"{s['mean_latency_ms']:.0f}" if s['mean_latency_ms'] is not None else "—",
            f"{s['mean_cost_usd']:.5f}" if s['mean_cost_usd'] is not None else "—",
            str(s["n_errors"]),
        ])
    widths = [max(len(str(r[i])) for r in [headers] + rows) for i in range(len(headers))]
    fmt = "  ".join(f"{{:<{w}}}" for w in widths)
    print()
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for r in rows:
        print(fmt.format(*r))
    print()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", type=Path, default=DEFAULT_QUESTIONS)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--pipelines", nargs="*", default=None,
                        help="Subset of pipelines to run (default: all in /benchmark)")
    parser.add_argument("--skip-judge", action="store_true")
    parser.add_argument("--skip-bertscore", action="store_true")
    parser.add_argument("--output", type=Path, default=None,
                        help="Where to save the JSON report (default: tests/accuracy_results_<ts>.json)")
    parser.add_argument("--graphrag-config", type=str, default=None,
                        help='JSON dict of Pipeline 3 retrieval tuning params, e.g. \'{"combine":true,"top_k":3}\'')
    parser.add_argument("--judge-consensus", type=int, default=1,
                        help='Run judge N times per (pred,ref) pair and take the majority verdict. '
                             'N>1 cuts judge variance dramatically. Default 1 (single call).')
    parser.add_argument("--judge-retry-on-error", type=int, default=2,
                        help='Number of retries on per-question judge errors (e.g. transient HF 5xx). '
                             'Default 2. Set 0 to fail fast.')
    args = parser.parse_args()

    graphrag_config = json.loads(args.graphrag_config) if args.graphrag_config else None
    if graphrag_config:
        logger.info("Using graphrag_config: %s", graphrag_config)

    questions = json.loads(args.questions.read_text(encoding="utf-8"))
    logger.info("Loaded %d questions from %s", len(questions), args.questions)

    per_question: list[dict[str, Any]] = []
    for i, q in enumerate(questions, 1):
        logger.info("[%d/%d] %s", i, len(questions), q["question"])
        try:
            results = run_pipelines(args.api, q["question"], args.pipelines, graphrag_config)
        except Exception as e:
            logger.error("Pipeline call failed for q%d: %s", q["id"], e)
            continue

        for pipe in results:
            if pipe.get("error"):
                pipe["grading"] = {"skipped": "pipeline error"}
                continue
            pipe["grading"] = grade_one(
                q["question"], q["reference"], pipe.get("answer", ""),
                skip_judge=args.skip_judge, skip_bertscore=args.skip_bertscore,
                judge_consensus_n=args.judge_consensus,
            )
            logger.info("    %-12s judge=%s f1r=%s tok=%s",
                        pipe["pipeline"],
                        pipe["grading"].get("judge_pass"),
                        pipe["grading"].get("bertscore_f1_rescaled"),
                        pipe["total_tokens"])

        per_question.append({
            "id": q["id"],
            "category": q.get("category"),
            "question": q["question"],
            "reference": q["reference"],
            "pipelines": results,
        })

    summary = aggregate(per_question)
    print_report(summary)

    output = args.output or RESULTS_DIR / f"accuracy_results_{int(time.time())}.json"
    output.write_text(
        json.dumps({"summary": summary, "results": per_question}, indent=2),
        encoding="utf-8",
    )
    logger.info("Saved report -> %s", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
