"""
Ingest data/raw_articles/ into TigerGraph via the GraphRAG service for Pipeline 3.

Why this design: Savanna's TigerGraph instance lives in the cloud and cannot
read files from the local graphrag container's filesystem. The upstream
"local" data_source path uses RUN LOADING JOB USING $DocumentContent:/path
which fails ("datasource not found") against Savanna. Instead, we mimic
what the upstream BDA/S3 code path does: stream each document directly to
TigerGraph via runLoadingJobWithData() — a single REST call per document
that doesn't require shared filesystem access.

Steps:
  1. POST /{graphname}/supportai/initialize once (idempotent) — sets up
     schema, indices, and the load_documents_content_json loading job.
     This is done via the GraphRAG service so we benefit from its
     orchestration of GDS/embedding-store init.
  2. For each raw article, build the {doc_id, doc_type, content} payload
     and POST it directly to TG via pyTigerGraph's runLoadingJobWithData.
     TigerGraph's loading job then triggers the GraphRAG ECC service,
     which does entity extraction via the configured LLM (Groq Llama 3.3
     70B) — this is the slow part.

Wall-clock: ~30s-1min per article on Groq free tier (chunked + entity
extraction per chunk). Full 432-article corpus: 4-8hr. Use --limit for
smoke testing.

Usage:
    python scripts/ingest_graphrag.py --limit 5     # smoke test
    python scripts/ingest_graphrag.py                # full corpus
    python scripts/ingest_graphrag.py --skip-init    # if schema already created
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


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest_graphrag")


ARTICLES_DIR = REPO_ROOT / "data" / "raw_articles"

# Constants set by the upstream initialize step. Hardcoded because we know
# from supportai.py:512-513 that local-mode create_ingest always returns
# these exact values.
LOAD_JOB_ID = "load_documents_content_json"
DATA_SOURCE_VAR = "DocumentContent"


def get_tg_connection():
    """Build a pyTigerGraph connection from server_config.json + .env."""
    # We read server_config.json directly because it has the JWT we just
    # generated and the Savanna hostname. backend/.env stores the local
    # graphrag-service URL, not the underlying TG URL.
    cfg_path = REPO_ROOT / "infra" / "graphrag-deploy" / "configs" / "server_config.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    db = cfg["db_config"]

    from pyTigerGraph import TigerGraphConnection

    conn = TigerGraphConnection(
        host=db["hostname"],
        graphname=settings.tg_graph_name,
        username=db.get("username", "tigergraph"),
        password=db.get("password", ""),
        gsPort=db.get("gsPort", "443"),
        restppPort=db.get("restppPort", "443"),
        apiToken=db.get("apiToken", ""),
    )
    return conn


def initialize_graph(graphname: str) -> None:
    """Call /supportai/initialize via the GraphRAG service. Idempotent."""
    url = f"{settings.tg_graphrag_url}/{graphname}/supportai/initialize"
    auth = (settings.tg_username, settings.tg_password)
    logger.info("POST %s", url)
    with httpx.Client(timeout=httpx.Timeout(600.0, connect=30.0), auth=auth) as c:
        r = c.post(url)
        if not r.is_success:
            logger.error("initialize failed: %s", r.text[:500])
            r.raise_for_status()
    logger.info("initialize OK")


def stream_documents(conn, files: list[Path]) -> tuple[int, int]:
    """Stream each article into TG via runLoadingJobWithData.

    The slow part isn't this HTTP call — it's the downstream entity
    extraction the ECC service triggers per chunk. The POST itself
    returns quickly; ECC processes asynchronously.

    Returns (succeeded, failed) counts.
    """
    ok = 0
    fail = 0
    for i, path in enumerate(files, 1):
        text = path.read_text(encoding="utf-8")
        if not text.strip():
            logger.warning("[%d/%d] empty %s", i, len(files), path.name)
            continue

        payload = json.dumps({
            "doc_id": path.stem,
            "doc_type": "",   # defaults to "semantic" chunker
            "content": text,
        })

        t0 = time.perf_counter()
        try:
            conn.runLoadingJobWithData(payload, DATA_SOURCE_VAR, LOAD_JOB_ID)
            dt = time.perf_counter() - t0
            ok += 1
            logger.info("[%d/%d] OK   %s (%.1fs, %d chars)",
                        i, len(files), path.stem, dt, len(text))
        except Exception as e:
            fail += 1
            logger.error("[%d/%d] FAIL %s — %s", i, len(files), path.stem, str(e)[:200])

    return ok, fail


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only ingest the first N articles (smoke testing)")
    parser.add_argument("--skip-init", action="store_true",
                        help="Skip /supportai/initialize (use if schema already exists)")
    parser.add_argument("--graphname", default=None,
                        help="Override graph name (default: settings.tg_graph_name)")
    parser.add_argument("--skip-ecc", action="store_true",
                        help="Skip auto-trigger of ECC consistency_update (you'll need to trigger manually)")
    parser.add_argument("--wait", action="store_true",
                        help="Block until ECC reports rebuild done (use for small batches; full corpus would block for hours)")
    parser.add_argument("--poll-interval", type=int, default=15, help="Seconds between status polls when --wait")
    parser.add_argument("--wait-timeout", type=int, default=14400, help="Max seconds to wait when --wait (default 4h)")
    args = parser.parse_args()

    graphname = args.graphname or settings.tg_graph_name

    files = sorted(ARTICLES_DIR.glob("*.txt"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        raise SystemExit(f"No .txt in {ARTICLES_DIR} — run scripts/fetch_dataset.py first")

    logger.info("graph=%s, %d articles to ingest", graphname, len(files))

    if not args.skip_init:
        initialize_graph(graphname)

    logger.info("Connecting to TigerGraph directly for streaming load...")
    conn = get_tg_connection()

    start = time.perf_counter()
    ok, fail = stream_documents(conn, files)
    elapsed = time.perf_counter() - start

    logger.info("=" * 60)
    logger.info("Ingested %d articles (%d failures) in %.1fs", ok, fail, elapsed)

    if not args.skip_ecc:
        trigger_ecc(graphname)
        if args.wait:
            poll_ecc_until_done(graphname, args.poll_interval, args.wait_timeout)
        else:
            logger.info("ECC processing in background. Watch with: docker logs -f devrag-graphrag-ecc")
            logger.info("Or check status: curl -u tigergraph:tigergraph http://localhost:8801/%s/graphrag/rebuild_status", graphname)
    return 0 if fail == 0 else 1


def trigger_ecc(graphname: str) -> None:
    """Manually trigger ECC graphrag run.

    The container's auto-startup ECC has an upstream async/sync bug
    ('coroutine' object has no attribute 'split'), so we always trigger
    via the on-demand consistency_update endpoint, which uses a different
    connection path that works.
    """
    url = f"http://localhost:8801/{graphname}/graphrag/consistency_update"
    auth = (settings.tg_username, settings.tg_password)
    logger.info("Triggering ECC: GET %s", url)
    with httpx.Client(timeout=30.0, auth=auth) as c:
        r = c.get(url)
        r.raise_for_status()
        logger.info("ECC trigger: %s", r.json())


def poll_ecc_until_done(graphname: str, interval: int, timeout: int) -> None:
    """Block until ECC reports rebuild done (or timeout)."""
    url = f"http://localhost:8801/{graphname}/graphrag/rebuild_status"
    auth = (settings.tg_username, settings.tg_password)
    deadline = time.time() + timeout
    last_status = None
    with httpx.Client(timeout=10.0, auth=auth) as c:
        while time.time() < deadline:
            try:
                r = c.get(url)
                r.raise_for_status()
                data = r.json()
                status = data.get("status")
                running = data.get("is_running")
                if status != last_status:
                    logger.info("ECC status: %s (running=%s)", status, running)
                    last_status = status
                if not running:
                    logger.info("ECC finished: %s", data)
                    return
            except Exception as e:
                logger.warning("ECC poll error: %s", e)
            time.sleep(interval)
    logger.error("ECC poll timed out after %ds", timeout)


if __name__ == "__main__":
    raise SystemExit(main())
