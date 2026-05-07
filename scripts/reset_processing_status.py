"""
Reset epoch_processed/epoch_processing on all DocumentChunks and Documents.

Why: during the bad-prompt era (when prompt_path pointed at the incomplete
llama_70b/ directory), entity extraction silently failed with "Invalid
template: None", but the chunks still got marked epoch_processed = now().
ECC then skips them on subsequent runs (see Scan_For_Updates.gsql) and
the graph never gets entities.

This script clears those flags so ECC re-processes everything from scratch
with the corrected prompts. Idempotent — safe to run multiple times.

Usage:
    python scripts/reset_processing_status.py            # dry run, prints counts
    python scripts/reset_processing_status.py --apply    # actually reset
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv

load_dotenv(REPO_ROOT / "backend" / ".env")


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


# Install + run an inline GSQL query that resets the epochs.
RESET_QUERY = """
CREATE OR REPLACE DISTRIBUTED QUERY Reset_Processing_Status(STRING v_type = "DocumentChunk") FOR GRAPH Nilanshgraph {
  SumAccum<INT> @@n_reset = 0;
  seeds = {v_type.*};
  reset = SELECT s FROM seeds:s
          WHERE s.epoch_processed != 0 OR s.epoch_processing != 0
          POST-ACCUM s.epoch_processed = 0,
                     s.epoch_processing = 0,
                     @@n_reset += 1;
  PRINT @@n_reset AS reset_count;
}
"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true",
                        help="Actually reset (default is dry-run / preview).")
    parser.add_argument("--vertex-types", nargs="+",
                        default=["DocumentChunk", "Document"],
                        help="Which vertex types to reset")
    args = parser.parse_args()

    conn = get_conn()

    print("Current vertex counts:")
    for vt in ["Document", "DocumentChunk", "Entity", "Community"]:
        try:
            print(f"  {vt:14s}: {conn.getVertexCount(vt)}")
        except Exception as e:
            print(f"  {vt:14s}: ERROR {str(e)[:80]}")

    if not args.apply:
        print()
        print("Dry run. Add --apply to actually reset epoch_processed/epoch_processing.")
        return 0

    # Install the query once (idempotent: CREATE OR REPLACE).
    print()
    print("Installing reset query...")
    install_res = conn.gsql(f"USE GRAPH Nilanshgraph\nBEGIN\n{RESET_QUERY}\nEND\nINSTALL QUERY Reset_Processing_Status")
    print(install_res[-400:] if isinstance(install_res, str) else install_res)

    for vt in args.vertex_types:
        print(f"\nResetting {vt}...")
        try:
            res = conn.runInstalledQuery("Reset_Processing_Status", {"v_type": vt})
            print(f"  {res}")
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\nDone. Re-trigger ECC:")
    print("  curl -u tigergraph:tigergraph http://localhost:8801/Nilanshgraph/graphrag/consistency_update")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
