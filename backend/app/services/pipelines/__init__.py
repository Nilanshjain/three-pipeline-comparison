"""
Pipeline package - the three RAG variants benchmarked side-by-side.

Each pipeline implements the Pipeline interface from base.py and returns
a uniform PipelineResult so the /benchmark/query endpoint can compare them.
"""

from app.services.pipelines.base import Pipeline, PipelineResult, RetrievedChunk

__all__ = ["Pipeline", "PipelineResult", "RetrievedChunk"]
