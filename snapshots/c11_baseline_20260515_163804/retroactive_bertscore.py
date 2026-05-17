"""
Compute BERTScore retroactively on a saved accuracy_results_*.json file.

Useful when the live pipelines are unhealthy but we already have their answers
saved from a previous run — we can still produce the BERTScore numbers needed
for the hackathon's bonus thresholds without re-running.

Usage:
    python backend/tests/retroactive_bertscore.py \
        --input backend/tests/accuracy_results_C2.json \
        --output backend/tests/accuracy_results_C2_with_bertscore.json
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "backend" / ".env")

from app.services.accuracy import bertscore_metrics

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("retroactive_bertscore")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    data = json.loads(args.input.read_text(encoding="utf-8"))
    results = data["results"]
    logger.info("loaded %d questions from %s", len(results), args.input)

    # Collect all (prediction, reference) pairs first, then BATCH the bert_score
    # call. Per-example calls cause the RoBERTa model to reload each time and
    # leak memory — segfaults on Windows around the 4th-5th call. Batching is
    # both reliable AND ~10x faster.
    pairs = []  # (q_id, pipeline_name, pred, ref)
    for r in results:
        ref = r["reference"]
        for p in r["pipelines"]:
            if p.get("error"):
                continue
            pred = p.get("answer", "")
            if not pred or not pred.strip():
                continue
            pairs.append((r["id"], p["pipeline"], pred, ref))

    logger.info("Collected %d (pipeline, question) pairs to score in batch", len(pairs))

    from bert_score import score as _score
    preds = [p[2] for p in pairs]
    refs = [p[3] for p in pairs]

    logger.info("Scoring batch — F1_raw...")
    _, _, f1_raw_t = _score(preds, refs, lang="en", rescale_with_baseline=False)
    logger.info("Scoring batch — F1_rescaled...")
    _, _, f1_resc_t = _score(preds, refs, lang="en", rescale_with_baseline=True)

    # Map results back into the data structure
    n = 0
    f1_raws = [float(x.item()) for x in f1_raw_t]
    f1_rescs = [float(x.item()) for x in f1_resc_t]
    for (qid, pname, _pr, _rf), f1r, f1c in zip(pairs, f1_raws, f1_rescs):
        for r in results:
            if r["id"] != qid:
                continue
            for p in r["pipelines"]:
                if p["pipeline"] == pname:
                    g = p.setdefault("grading", {})
                    g["bertscore_f1_raw"] = round(f1r, 4)
                    g["bertscore_f1_rescaled"] = round(f1c, 4)
                    n += 1
                    logger.info("Q%d / %s: f1_raw=%.3f f1_resc=%.3f", qid, pname, f1r, f1c)
                    break
            break

    # Recompute summary aggregates with BERTScore included.
    by_pipeline: dict[str, dict[str, list]] = {}
    for r in results:
        for p in r["pipelines"]:
            name = p["pipeline"]
            slot = by_pipeline.setdefault(name, {
                "judge_passes": [], "f1_raw": [], "f1_rescaled": [],
                "tokens": [], "latency_ms": [], "cost_usd": [], "errors": 0,
            })
            if p.get("error"):
                slot["errors"] += 1
                continue
            slot["tokens"].append(p["total_tokens"])
            slot["latency_ms"].append(p["latency_ms"])
            slot["cost_usd"].append(p["cost_usd"])
            grading = p.get("grading", {})
            if "judge_pass" in grading:
                slot["judge_passes"].append(bool(grading["judge_pass"]))
            if "bertscore_f1_raw" in grading:
                slot["f1_raw"].append(grading["bertscore_f1_raw"])
                slot["f1_rescaled"].append(grading["bertscore_f1_rescaled"])

    summary = {}
    for name, s in by_pipeline.items():
        nj = len(s["judge_passes"])
        nb = len(s["f1_raw"])
        summary[name] = {
            "n_questions": len(s["tokens"]) + s["errors"],
            "n_errors": s["errors"],
            "judge_pass_rate": (sum(s["judge_passes"]) / nj) if nj else None,
            "judge_n": nj,
            "bertscore_f1_raw_mean": (sum(s["f1_raw"]) / nb) if nb else None,
            "bertscore_f1_rescaled_mean": (sum(s["f1_rescaled"]) / nb) if nb else None,
            "mean_total_tokens": (sum(s["tokens"]) / len(s["tokens"])) if s["tokens"] else None,
            "mean_latency_ms": (sum(s["latency_ms"]) / len(s["latency_ms"])) if s["latency_ms"] else None,
            "mean_cost_usd": (sum(s["cost_usd"]) / len(s["cost_usd"])) if s["cost_usd"] else None,
        }

    data["summary"] = summary
    args.output.write_text(json.dumps(data, indent=2), encoding="utf-8")

    # Pretty-print summary
    print()
    print(f"{'pipeline':<10} {'judge%':>7} {'F1_resc':>8} {'F1_raw':>7} {'tokens':>7} {'latency':>9} {'errs':>5}")
    print("-" * 60)
    for name, m in summary.items():
        jp = f"{m['judge_pass_rate']*100:.1f}%" if m["judge_pass_rate"] is not None else "-"
        fr = f"{m['bertscore_f1_rescaled_mean']:.3f}" if m["bertscore_f1_rescaled_mean"] is not None else "-"
        fw = f"{m['bertscore_f1_raw_mean']:.3f}" if m["bertscore_f1_raw_mean"] is not None else "-"
        tok = f"{m['mean_total_tokens']:.0f}" if m["mean_total_tokens"] is not None else "-"
        lat = f"{m['mean_latency_ms']:.0f}" if m["mean_latency_ms"] is not None else "-"
        print(f"{name:<10} {jp:>7} {fr:>8} {fw:>7} {tok:>7} {lat:>9} {m['n_errors']:>5}")

    logger.info("graded %d (pipeline, question) pairs; saved -> %s", n, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
