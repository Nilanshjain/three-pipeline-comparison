"""
Application configuration management.

This module handles loading and validating all configuration settings
from environment variables and .env files.
"""

import os
from typing import Optional
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="allow"  # Allow extra fields from .env
    )

    # Database settings
    database_url: str = "postgresql://postgres:password@localhost:5432/precisionrag_dev"
    database_host: str = "localhost"
    database_port: int = 5432
    database_name: str = "precisionrag_dev"
    database_user: str = "postgres"
    database_password: str = "password"

    # Redis settings
    redis_url: str = "redis://localhost:6379"

    # AI API settings
    openai_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    google_api_key: Optional[str] = None
    groq_api_key: Optional[str] = None

    # LLM provider switch — all three pipelines read these.
    # provider: "groq" (default, zero-cost via Llama 3.3 70B free tier) or "gemini".
    # Keeping this configurable lets us flip back to Gemini in one env var if
    # Groq rate-limits us mid-eval.
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"

    # Hugging Face (used by LLM-as-Judge evaluator)
    hf_token: Optional[str] = None

    # TigerGraph GraphRAG (Pipeline 3)
    # GraphRAG runs locally via docker-compose (infra/graphrag-deploy/) and
    # connects to Savanna for the underlying TigerGraph database.
    tg_graphrag_url: str = "http://localhost:8800"  # host port we map to graphrag:8000
    tg_username: Optional[str] = None               # TigerGraph DB username (basic auth)
    tg_password: Optional[str] = None               # TigerGraph DB password (basic auth)
    tg_graph_name: str = "DevRAG"                   # graph name created in Savanna

    # Application settings
    environment: str = "development"
    debug: bool = True
    secret_key: str = "your-secret-key-for-jwt-tokens"

    # File upload settings
    max_file_size_mb: int = 10
    upload_dir: str = "uploads"

    # Vector embedding settings
    embedding_model: str = "all-MiniLM-L6-v2"  # Sentence transformer model
    embedding_dimension: int = 384  # Dimension of embeddings

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, v, info):
        """Build database URL from components if not provided directly."""
        if v == "postgresql://postgres:password@localhost:5432/precisionrag_dev":
            # Build from individual components
            values = info.data
            host = values.get("database_host", "localhost")
            port = values.get("database_port", 5432)
            name = values.get("database_name", "precisionrag_dev")
            user = values.get("database_user", "postgres")
            password = values.get("database_password", "password")
            return f"postgresql://{user}:{password}@{host}:{port}/{name}"
        return v

    @field_validator("upload_dir")
    @classmethod
    def create_upload_dir(cls, v):
        """Ensure upload directory exists."""
        if not os.path.exists(v):
            os.makedirs(v, exist_ok=True)
        return v


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance."""
    return settings