"""
Identify and (optionally) delete bad-quality entities created during the
brief Llama 3.1 8B extraction phase.

Heuristics for "bad":
- vertex_id length <= 2 chars (single letters, fragments)
- vertex_id is a single special character (π, τ, etc. — model token noise)
- vertex_id matches "chunk_\d+" pattern (model confused chunk IDs with entities)
- vertex_id is a stopword/fragment ('arg', 'foo', 'this', 'and', 'the', etc.)
- vertex_id contains a URL fragment (https:__... — bad escaping)

Good entities (kept):
- Multi-word person/place/concept names: 'geoffrey-hinton', 'imitation-learning'
- Multi-word technical terms: 'denoising-autoencoders', 'discrete-channel'

Usage:
    python scripts/clean_bad_entities.py            # dry run — list candidates
    python scripts/clean_bad_entities.py --apply    # actually delete
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "backend" / ".env")


# Generic stopwords / fragments observed in 8B garbage output
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for",
    "is", "it", "this", "that", "these", "those",
    "arg", "foo", "bar", "baz",
    "d", "t", "s", "n", "w", "x", "y", "z",
    "h59", "gcn",  # specific examples we saw
}

# Special chars that 8B sometimes emits as "entities"
SPECIAL_CHAR_PATTERN = re.compile(r"^[^\w-]+$")  # only non-word chars
CHUNK_ID_PATTERN = re.compile(r"_chunk_\d+$")    # 'something_chunk_3'
URL_FRAGMENT_PATTERN = re.compile(r"^https?[_:]")  # 'https:__...' or 'http_..'


def is_bad_entity(vid: str) -> tuple[bool, str]:
    """Return (is_bad, reason). reason is empty if good."""
    if not vid:
        return True, "empty id"
    v = vid.strip()
    if len(v) <= 2:
        return True, f"too short ({len(v)} chars)"
    if v.lower() in STOPWORDS:
        return True, "stopword"
    if SPECIAL_CHAR_PATTERN.match(v):
        return True, "only special chars"
    if CHUNK_ID_PATTERN.search(v):
        return True, "looks like a chunk id"
    if URL_FRAGMENT_PATTERN.match(v):
        return True, "URL fragment"
    return False, ""


def get_conn():
    cfg = json.loads((REPO_ROOT / "infra" / "graphrag-deploy" / "configs" / "server_config.json").read_text())
    db = cfg["db_config"]
    from pyTigerGraph import TigerGraphConnection
    return TigerGraphConnection(
        host=db["hostname"],
        graphname="Nilanshgraph",
        username=db["username"],
        password=db["password"],
        gsPort=db["gsPort"],
        restppPort=db["restppPort"],
        apiToken=db["apiToken"],
    )


# GSQL query: scan all Entity vertices, return ids. Avoids accumulator-pretty-print
# issues by just printing the raw set.
SCAN_QUERY = """
INTERPRET QUERY () FOR GRAPH Nilanshgraph {
  SetAccum<STRING> @@ids;
  S = {Entity.*};
  s_post = SELECT v FROM S:v POST-ACCUM @@ids += v.id;
  PRINT @@ids;
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually delete the bad entities (default is dry run)")
    parser.add_argument("--max-list", type=int, default=80,
                        help="How many bad entities to print")
    args = parser.parse_args()

    conn = get_conn()
    print(f"Total entities BEFORE: {conn.getVertexCount('Entity')}")

    res = conn.runInterpretedQuery(SCAN_QUERY)
    all_ids = res[0]["@@ids"]
    print(f"Fetched {len(all_ids)} entity ids from graph")

    bad = []
    good = []
    for vid in all_ids:
        is_bad, reason = is_bad_entity(vid)
        (bad if is_bad else good).append((vid, reason))

    print(f"\nClassification: {len(good)} good, {len(bad)} bad")
    print(f"\nBad entities (first {min(len(bad), args.max_list)}):")
    for vid, reason in bad[: args.max_list]:
        print(f"  - {vid!r:50s}  ({reason})")

    print(f"\nGood entities (sample of 10):")
    for vid, _ in good[:10]:
        print(f"  + {vid!r}")

    if not args.apply:
        print("\nDry run. Add --apply to actually delete bad entities.")
        return 0

    if not bad:
        print("\nNo bad entities to delete.")
        return 0

    print(f"\nDeleting {len(bad)} bad entities...")
    # delVerticesById takes a list of IDs
    bad_ids = [vid for vid, _ in bad]
    # Delete in batches to avoid massive payloads
    BATCH = 50
    deleted = 0
    for i in range(0, len(bad_ids), BATCH):
        batch = bad_ids[i: i + BATCH]
        try:
            n = conn.delVerticesById("Entity", batch)
            deleted += n if isinstance(n, int) else len(batch)
            print(f"  batch {i//BATCH + 1}: deleted {len(batch)} ({deleted} cumulative)")
        except Exception as e:
            print(f"  batch {i//BATCH + 1}: ERROR {str(e)[:120]}")

    print(f"\nTotal entities AFTER: {conn.getVertexCount('Entity')}")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
