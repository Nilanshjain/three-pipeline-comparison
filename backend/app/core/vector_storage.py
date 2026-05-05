"""
Vector storage implementation using PostgreSQL without pgvector.

This module provides vector storage and similarity search using standard PostgreSQL
features. Can be upgraded to pgvector later for better performance.
"""

import numpy as np
from typing import List, Tuple, Optional, Dict, Any
from sqlalchemy import Column, Integer, Text, ARRAY, Float, DateTime, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
import json
import logging


def _cosine_similarity(query: np.ndarray, doc: np.ndarray) -> float:
    """Numpy-only cosine, used in place of sklearn to keep module-load light."""
    qn = np.linalg.norm(query)
    dn = np.linalg.norm(doc)
    if qn == 0 or dn == 0:
        return 0.0
    return float(np.dot(query, doc) / (qn * dn))

from .database import Base

logger = logging.getLogger(__name__)


class VectorDocument(Base):
    """
    Document storage with vector embeddings using standard PostgreSQL.

    This table stores documents and their vector embeddings as JSON/array columns
    until we can install pgvector extension.
    """
    __tablename__ = "vector_documents"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(Text, nullable=False)
    content = Column(Text, nullable=False)
    embedding_json = Column(Text, nullable=True)  # JSON string of embedding vector
    chunk_index = Column(Integer, nullable=False, default=0)
    chunk_text = Column(Text, nullable=False)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

    def set_embedding(self, embedding: List[float]):
        """Store embedding as JSON string."""
        self.embedding_json = json.dumps(embedding)

    def get_embedding(self) -> Optional[List[float]]:
        """Retrieve embedding from JSON string."""
        if self.embedding_json:
            return json.loads(self.embedding_json)
        return None


class PostgreSQLVectorStorage:
    """
    Vector storage and similarity search using standard PostgreSQL.

    This class provides vector operations without requiring pgvector extension.
    It's designed to be easily upgradeable to pgvector when available.
    """

    def __init__(self, db_session: Session):
        self.db = db_session

    def store_document_with_embeddings(
        self,
        filename: str,
        content: str,
        chunks: List[str],
        embeddings: List[List[float]]
    ) -> List[int]:
        """
        Store document chunks with their embeddings.

        Args:
            filename: Name of the source file
            content: Full document content
            chunks: List of text chunks
            embeddings: List of embedding vectors (one per chunk)

        Returns:
            List of document IDs created
        """
        document_ids = []

        try:
            for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
                doc = VectorDocument(
                    filename=filename,
                    content=content,
                    chunk_index=i,
                    chunk_text=chunk
                )
                doc.set_embedding(embedding)

                self.db.add(doc)
                self.db.flush()  # Get the ID
                document_ids.append(doc.id)

            self.db.commit()
            logger.info(f"Stored {len(document_ids)} chunks for {filename}")
            return document_ids

        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to store document {filename}: {e}")
            raise

    def similarity_search(
        self,
        query_embedding: List[float],
        limit: int = 5,
        similarity_threshold: float = 0.5,
        filename_filter: Optional[str] = None
    ) -> List[Tuple[VectorDocument, float]]:
        """
        Find similar documents using cosine similarity.

        Args:
            query_embedding: Vector representation of the query
            limit: Maximum number of results to return
            similarity_threshold: Minimum similarity score

        Returns:
            List of (document, similarity_score) tuples, sorted by similarity
        """
        try:
            # Get all documents with embeddings, optionally filtered by filename
            query = self.db.query(VectorDocument).filter(
                VectorDocument.embedding_json.isnot(None)
            )

            if filename_filter:
                query = query.filter(VectorDocument.filename == filename_filter)
                logger.info(f"Filtering search to document: {filename_filter}")

            documents = query.all()

            if not documents:
                if filename_filter:
                    logger.warning(f"No documents found for filename: {filename_filter}")
                else:
                    logger.warning("No documents with embeddings found")
                return []

            # Calculate similarities
            results = []
            all_similarities = []
            query_vec_flat = np.array(query_embedding)
            for doc in documents:
                doc_embedding = doc.get_embedding()
                if doc_embedding:
                    doc_vec_flat = np.array(doc_embedding)
                    similarity = _cosine_similarity(query_vec_flat, doc_vec_flat)
                    all_similarities.append(similarity)

                    if similarity >= similarity_threshold:
                        results.append((doc, float(similarity)))

            # Log similarity stats for debugging
            if all_similarities:
                logger.info(f"Similarity scores - Min: {min(all_similarities):.3f}, Max: {max(all_similarities):.3f}, Avg: {sum(all_similarities)/len(all_similarities):.3f}")
                logger.info(f"Threshold: {similarity_threshold}, Matches above threshold: {len(results)}")

            # Sort by similarity (highest first)
            results.sort(key=lambda x: x[1], reverse=True)

            # Return top results
            top_results = results[:limit]
            logger.info(f"Found {len(top_results)} similar documents out of {len(documents)} total")
            return top_results

        except Exception as e:
            logger.error(f"Similarity search failed: {e}")
            raise

    def get_document_by_id(self, doc_id: int) -> Optional[VectorDocument]:
        """Retrieve a document by its ID."""
        return self.db.query(VectorDocument).filter(VectorDocument.id == doc_id).first()

    def delete_document(self, filename: str) -> int:
        """
        Delete all chunks for a document.

        Returns:
            Number of chunks deleted
        """
        try:
            deleted_count = self.db.query(VectorDocument).filter(
                VectorDocument.filename == filename
            ).delete()
            self.db.commit()
            logger.info(f"Deleted {deleted_count} chunks for {filename}")
            return deleted_count
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete document {filename}: {e}")
            raise

    def list_documents(self) -> List[Dict[str, Any]]:
        """
        List all stored documents with metadata.

        Returns:
            List of document summaries
        """
        try:
            # Group chunks by filename
            from sqlalchemy import distinct

            filenames = self.db.query(distinct(VectorDocument.filename)).all()

            documents = []
            for (filename,) in filenames:
                chunks = self.db.query(VectorDocument).filter(
                    VectorDocument.filename == filename
                ).all()

                documents.append({
                    "filename": filename,
                    "chunk_count": len(chunks),
                    "total_characters": sum(len(chunk.chunk_text) for chunk in chunks),
                    "created_at": min(chunk.created_at for chunk in chunks),
                    "has_embeddings": all(chunk.embedding_json for chunk in chunks)
                })

            return documents

        except Exception as e:
            logger.error(f"Failed to list documents: {e}")
            raise

    def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage statistics."""
        try:
            total_documents = self.db.query(VectorDocument.filename).distinct().count()
            total_chunks = self.db.query(VectorDocument).count()
            chunks_with_embeddings = self.db.query(VectorDocument).filter(
                VectorDocument.embedding_json.isnot(None)
            ).count()

            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "chunks_with_embeddings": chunks_with_embeddings,
                "embedding_coverage": chunks_with_embeddings / total_chunks if total_chunks > 0 else 0,
                "storage_type": "PostgreSQL JSON (upgradeable to pgvector)"
            }
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}


def upgrade_to_pgvector(db_session: Session) -> bool:
    """
    Upgrade to pgvector when the extension becomes available.

    This function will:
    1. Check if pgvector is available
    2. Create new vector column
    3. Migrate existing embeddings
    4. Update the model

    Returns:
        True if upgrade successful, False otherwise
    """
    try:
        # Test if pgvector is available
        db_session.execute("SELECT '[1,2,3]'::vector")

        logger.info("pgvector extension detected! Starting upgrade...")

        # Add vector column to existing table
        db_session.execute("""
            ALTER TABLE vector_documents
            ADD COLUMN IF NOT EXISTS embedding_vector vector(384)
        """)

        # Migrate existing JSON embeddings to vector column
        documents = db_session.query(VectorDocument).filter(
            VectorDocument.embedding_json.isnot(None)
        ).all()

        for doc in documents:
            embedding = doc.get_embedding()
            if embedding:
                # Convert to vector format
                vector_str = '[' + ','.join(map(str, embedding)) + ']'
                db_session.execute(
                    "UPDATE vector_documents SET embedding_vector = %s::vector WHERE id = %s",
                    (vector_str, doc.id)
                )

        db_session.commit()
        logger.info(f"Successfully upgraded {len(documents)} embeddings to pgvector!")
        return True

    except Exception as e:
        logger.warning(f"pgvector upgrade not available: {e}")
        return False