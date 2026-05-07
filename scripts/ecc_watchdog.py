"""
ECC watchdog — keeps the GraphRAG entity-extraction loop alive overnight.

What it does:
  - Polls /Nilanshgraph/graphrag/rebuild_status every N seconds.
  - When is_running=false but the graph still has DocumentChunks without
    extracted entities, it auto-fires /consistency_update to resume.
  - Logs entity / community counts on a slower cadence so you can wake up
    in the morning and see progress.

Why this exists:
  - The upstream ECC's lifespan auto-start is broken (sync-call on async
    conn). Manual triggers are needed after every container restart.
  - If Docker Desktop restarts (Windows update, sleep), or Savanna
    idle-suspends, ECC silently stops mid-run.
  - Groq's RPD limits can stall ECC for ~hours at a time on free tier;
    the rebuild_status will report is_running=false during long backoff.

Usage:
    python scripts/ecc_watchdog.py                    # poll every 60s
    python scripts/ecc_watchdog.py --interval 30      # tighter loop
    python scripts/ecc_watchdog.py --once             # one-shot trigger then exit

Run it alongside the docker stack — `nohup python ... &` or in a separate
terminal window. Use Ctrl+C to stop. Idempotent: safe to start/stop any
number of times.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

import httpx
from dotenv import load_dotenv

load_dotenv(REPO_ROOT / "backend" / ".env")

from app.core.config import settings  # noqa: E402


logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s [watchdog] %(message)s",
                    datefmt="%H:%M:%S")
logger = logging.getLogger("ecc_watchdog")


ECC_BASE = "http://localhost:8801"
GRAPHRAG_BASE = "http://localhost:8800"
STATUS_PATH = "/Nilanshgraph/graphrag/rebuild_status"
TRIGGER_PATH = "/Nilanshgraph/graphrag/consistency_update"

# Resync graph counts every N polls (don't hit TG REST too often).
COUNT_POLL_EVERY = 5


def get_status(client: httpx.Client) -> dict:
    r = client.get(f"{ECC_BASE}{STATUS_PATH}", auth=(settings.tg_username, settings.tg_password))
    r.raise_for_status()
    return r.json()


def trigger(client: httpx.Client) -> dict:
    logger.info("Triggering ECC: GET %s", TRIGGER_PATH)
    r = client.get(f"{ECC_BASE}{TRIGGER_PATH}", auth=(settings.tg_username, settings.tg_password))
    r.raise_for_status()
    return r.json()


def graph_counts() -> dict:
    """Return current vertex counts. Returns empty dict on transient errors so
    a single failure doesn't kill the loop."""
    cfg_path = REPO_ROOT / "infra" / "graphrag-deploy" / "configs" / "server_config.json"
    try:
        cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
        db = cfg["db_config"]
        from pyTigerGraph import TigerGraphConnection
        c = TigerGraphConnection(
            host=db["hostname"],
            graphname="Nilanshgraph",
            username=db["username"],
            password=db["password"],
            gsPort=db["gsPort"],
            restppPort=db["restppPort"],
            apiToken=db["apiToken"],
        )
        return {
            "docs": c.getVertexCount("Document"),
            "chunks": c.getVertexCount("DocumentChunk"),
            "entities": c.getVertexCount("Entity"),
            "communities": _safe_count(c, "Community"),
        }
    except Exception as e:
        logger.warning("count fetch failed: %s", str(e)[:120])
        return {}


def _safe_count(conn, vtype: str) -> int:
    try:
        return conn.getVertexCount(vtype)
    except Exception:
        return 0  # vertex type may not exist yet


def loop(interval: int, max_iters: int | None = None) -> int:
    iters = 0
    last_counts: dict = {}
    with httpx.Client(timeout=30.0) as client:
        while True:
            iters += 1
            try:
                st = get_status(client)
            except Exception as e:
                logger.warning("status fetch failed: %s — will retry", str(e)[:120])
                time.sleep(interval)
                continue

            running = st.get("is_running")
            status = st.get("status")

            if iters % COUNT_POLL_EVERY == 1:
                counts = graph_counts()
                if counts:
                    delta = ""
                    if last_counts:
                        de = counts["entities"] - last_counts.get("entities", 0)
                        delta = f" (Δentities={de:+d})"
                    logger.info(
                        "running=%s status=%s | docs=%s chunks=%s entities=%s communities=%s%s",
                        running, status, counts.get("docs"), counts.get("chunks"),
                        counts.get("entities"), counts.get("communities"), delta,
                    )
                    last_counts = counts
                else:
                    logger.info("running=%s status=%s (counts unavailable)", running, status)
            else:
                logger.info("running=%s status=%s", running, status)

            # Decision: trigger if stopped, regardless of why.
            # Worst case if work is already done: a trigger is cheap (idempotent
            # on already-processed chunks via the has_embeddings check).
            if running is False:
                try:
                    resp = trigger(client)
                    logger.info("trigger response: %s", resp)
                except Exception as e:
                    logger.error("trigger failed: %s", str(e)[:200])

            if max_iters and iters >= max_iters:
                return 0
            time.sleep(interval)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=int, default=60,
                        help="Seconds between status polls (default 60)")
    parser.add_argument("--once", action="store_true",
                        help="Run one poll, trigger if needed, then exit")
    args = parser.parse_args()

    logger.info("starting watchdog (interval=%ds)", args.interval)
    return loop(args.interval, max_iters=1 if args.once else None)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        logger.info("stopped by user")
        raise SystemExit(0)
