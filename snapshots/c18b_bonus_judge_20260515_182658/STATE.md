# C18b snapshot — 92.9% judge, ~1434 tokens

This was the FIRST run that crossed the bonus judge threshold (≥90%).

Tally:
- judge: 92.9% (13/14) — bonus criterion MET
- F1_raw: 0.861 (vs 0.88 needed) — bonus criterion MISSED by 0.019
- F1_resc: 0.178 (vs 0.55 needed) — bonus criterion MISSED
- tokens: 1434 (vs 1400 Basic RAG) — +2.4% over (token reduction MISSED)

Code state: adaptive_fallback=True via API config; NO trim_answer. Refusal patterns include only the conservative set (Q7 false-positive eliminated).

This snapshot exists so we can compare against C19 (added trim_answer) and pick whichever is better for final submission.
