"""Modèles de données ODM Beanie pour MongoDB.

Conformité CDC (§8.2) :
- LogEntry : journalisation des événements avec index composé et index TTL.
- InboundMessage : traçabilité des messages reçus avec index unique wamid.
- UserProfile : profil pseudonyme de l'utilisateur (user_hash).
- HealthFacility & EmergencyContact : répertoires vérifiés de santé et urgences.
- AnswerTrace : trace technique des réponses (chunks RAG, tokens, timings).
"""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated

from beanie import Document, Indexed
from pydantic import Field
from pymongo import ASCENDING, IndexModel


def utcnow() -> datetime:
    """Retourne la date et heure actuelles en UTC."""
    return datetime.now(UTC)


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"


class LogSource(StrEnum):
    WEBHOOK = "webhook"
    WORKER = "worker"
    SCRAPER = "scraper"
    SCHEDULER = "scheduler"


class LogEntry(Document):
    """Journal des événements de l'application."""

    timestamp: datetime = Field(default_factory=utcnow)
    level: LogLevel = LogLevel.INFO
    source: LogSource = LogSource.WEBHOOK
    event: str
    message_id: str | None = None  # wamid WhatsApp
    endpoint: str | None = None
    status_code: int | None = None
    duration_ms: float | None = None
    detail: dict | None = None  # Aucun texte utilisateur en clair

    class Settings:
        name = "logs"
        indexes = [
            IndexModel([("message_id", ASCENDING), ("timestamp", ASCENDING)]),
            IndexModel(
                [("timestamp", ASCENDING)],
                expireAfterSeconds=30 * 24 * 3600,
                name="ttl_timestamp",
            ),
        ]


class MessageState(StrEnum):
    RECEIVED = "received"
    QUEUED = "queued"
    PROCESSING = "processing"
    REPLIED = "replied"
    FAILED = "failed"
    IGNORED = "ignored"


class InboundMessage(Document):
    """Suivi d'état et d'idempotence des messages entrants."""

    wamid: Annotated[str, Indexed(unique=True)]
    user_hash: str
    message_type: str = "text"
    state: MessageState = MessageState.RECEIVED
    attempts: int = 0
    received_at: datetime = Field(default_factory=utcnow)
    replied_at: datetime | None = None
    error: str | None = None

    class Settings:
        name = "inbound_messages"
        indexes = [
            IndexModel([("received_at", ASCENDING)], expireAfterSeconds=30 * 24 * 3600),
        ]


class UserProfile(Document):
    """Profil pseudonyme de l'utilisateur (zéro PII stockée)."""

    user_hash: Annotated[str, Indexed(unique=True)]
    preferred_language: str | None = "fr"  # "fr", "wo"
    consent_at: datetime | None = None
    opted_out: bool = False
    created_at: datetime = Field(default_factory=utcnow)
    last_seen_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "user_profiles"


class HealthFacility(Document):
    """Établissement ou relais de santé vérifié."""

    name: str
    facility_type: str
    region: str
    locality: str | None = None
    phone: str | None = None
    address: str | None = None
    opening_hours: str | None = None
    verified_at: datetime | None = None
    source: str | None = None
    active: bool = True

    class Settings:
        name = "health_facilities"
        indexes = [
            IndexModel([("region", ASCENDING), ("active", ASCENDING)]),
        ]


class EmergencyContact(Document):
    """Coordonnées d'urgence vérifiées (non générées par LLM)."""

    zone: str
    label: str
    phone: str
    verified_at: datetime = Field(default_factory=utcnow)
    verified_by_role: str = "référent médical"

    class Settings:
        name = "emergency_contacts"


class AnswerTrace(Document):
    """Trace d'audit technique d'une réponse générée."""

    wamid: Annotated[str, Indexed(unique=True)]
    language: str
    intent: str | None = None
    safety_flags: list[str] = Field(default_factory=list)
    chunk_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    model_id: str | None = None
    prompt_version: str | None = None
    corpus_version: str | None = None
    guardrail_passed: bool | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    duration_ms: float | None = None
    created_at: datetime = Field(default_factory=utcnow)

    class Settings:
        name = "answer_traces"
