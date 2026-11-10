"""Module de configuration générale de l'application Lafiya.

Valide et charge les variables d'environnement via pydantic-settings
selon les spécifications du CDC (§11).
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Configuration validée de l'application."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Environnement général
    ENVIRONMENT: Literal["development", "staging", "production"] = "development"
    DEBUG: bool = False

    # Base de données MongoDB Atlas (§4.1, §8)
    MONGODB_URI: str
    MONGODB_DB: str = "lafiya_db"

    # File de tâches & Déduplication Redis (§4.1, §5.3)
    REDIS_URL: str = "redis://localhost:6379/0"
    DEDUP_TTL_SECONDS: int = 604800  # 7 jours minimum (fenêtre Meta)

    # Base vectorielle Qdrant Cloud (§4.1, §6.3, §7.4)
    QDRANT_URL: str
    QDRANT_API_KEY: str
    QDRANT_COLLECTION: str = "lafiya_corpus_who"

    # Embeddings & LLM (§4.1, §6.4)
    OPENAI_API_KEY: str = Field(default="")
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    ANTHROPIC_API_KEY: str = Field(default="")
    LLM_MODEL: str = "claude-3-5-haiku-20241022"

    # Meta WhatsApp Cloud API (§5.1, §5.2)
    WHATSAPP_VERIFY_TOKEN: str = Field(default="")
    WHATSAPP_APP_SECRET: str = Field(default="")
    WHATSAPP_ACCESS_TOKEN: str = Field(default="")
    WHATSAPP_PHONE_NUMBER_ID: str = Field(default="")

    # Pseudonymisation & Sécurité (§10.4)
    USER_HASH_SECRET: str

    # Observabilité LangFuse (§4.1, §9.9)
    LANGFUSE_PUBLIC_KEY: str = Field(default="")
    LANGFUSE_SECRET_KEY: str = Field(default="")
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"

    # Paramètres RAG & Rate Limiting (§6.3, §10.5)
    RAG_TOP_K: int = 4
    RAG_SCORE_THRESHOLD: float = 0.72
    RATE_LIMIT_PER_MINUTE: int = 10
    RATE_LIMIT_PER_DAY: int = 100

    # Journalisation (§9.10)
    LOG_LEVEL: str = "INFO"
    LOG_BUFFER_SIZE: int = 50
    LOG_FLUSH_INTERVAL: int = 5
    LOG_RETENTION_DAYS: int = 30


@lru_cache
def get_settings() -> Settings:
    """Retourne l'instance unique des paramètres mise en cache."""
    return Settings()
