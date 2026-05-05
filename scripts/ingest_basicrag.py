"""
Ingest data/raw_articles/ into Postgres for Pipeline 2 (Basic RAG).

Reads each .txt, chunks it, embeds via sentence-transformers, stores in
the vector_documents table. Idempotent: skip files whose filename is
already present (use --refresh to force re-ingest).

Usage:
    python scripts/ingest_basicrag.py
    python scripts/ingest_basicrag.py --limit 10
    python scripts/ingest_basicrag.py --refresh
    python scripts/ingest_basicrag.py --strategy paragraph
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# Run from repo root: import the backend app
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "backend"))

from dotenv import load_dotenv
load_dotenv(REPO_ROOT / "backend" / ".env")

from sqlalchemy import distinct

from app.core.database import create_tables, get_db
from app.core.vector_storage import PostgreSQLVectorStorage, VectorDocument
from app.services.chunking import DocumentChunker
from app.services.embeddings import get_embedding_service


logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ingest")


ARTICLES_DIR = REPO_ROOT / "data" / "raw_articles"


def already_ingested(db) -> set[str]:
    rows = db.query(distinct(VectorDocument.filename)).all()
    return {r[0] for r in rows}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--strategy", default="smart",
                        choices=["smart", "paragraph", "sentence", "fixed"])
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--refresh", action="store_true",
                        help="Delete existing chunks for each filename before re-ingesting")
    args = parser.parse_args()

    if not ARTICLES_DIR.exists():
        logger.error("No articles found at %s — run scripts/fetch_dataset.py first", ARTICLES_DIR)
        return 1

    files = sorted(ARTICLES_DIR.glob("*.txt"))
    if args.limit:
        files = files[: args.limit]
    if not files:
        logger.error("No .txt files in %s", ARTICLES_DIR)
        return 1

    logger.info("Initialising database…")
    create_tables()

    logger.info("Loading embedding service (sentence-transformers all-MiniLM-L6-v2)…")
    embedder = get_embedding_service()

    chunker = DocumentChunker(
        chunk_size=args.chunk_size,
        chunk_overlap=args.chunk_overlap,
    )

    db = next(get_db())
    store = PostgreSQLVectorStorage(db)

    existing = already_ingested(db) if not args.refresh else set()
    logger.info("Already in DB: %d filenames", len(existing))

    total_chunks = 0
    total_docs = 0
    start = time.perf_counter()

    for i, path in enumerate(files, 1):
        if path.name in existing:
            logger.info("[%d/%d] cached %s", i, len(files), path.name)
            continue

        if args.refresh:
            store.delete_document(path.name)

        text = path.read_text(encoding="utf-8")
        chunks = chunker.chunk_text(text, source_file=path.name, strategy=args.strategy)
        if not chunks:
            logger.warning("[%d/%d] empty %s", i, len(files), path.name)
            continue

        chunk_texts = [c.text for c in chunks]
        embeddings = embedder.generate_embeddings(chunk_texts)
        store.store_document_with_embeddings(
            filename=path.name,
            content=text,
            chunks=chunk_texts,
            embeddings=embeddings,
        )
        total_chunks += len(chunks)
        total_docs += 1
        logger.info("[%d/%d] %s → %d chunks", i, len(files), path.name, len(chunks))

    elapsed = time.perf_counter() - start
    logger.info("Done. %d docs / %d chunks in %.1fs", total_docs, total_chunks, elapsed)

    stats = store.get_storage_stats()
    logger.info("Storage stats: %s", stats)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
