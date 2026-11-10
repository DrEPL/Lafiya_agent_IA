"""Point d'entrée principal de l'application FastAPI Lafiya.

Gère le cycle de vie applicatif (lifespan) :
- Initialisation de la connexion MongoDB et de l'ODM Beanie.
- Enregistrement des routes API (health, webhook).
- Fermeture propre des connexions à l'arrêt.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any, cast

from beanie import init_beanie
from fastapi import FastAPI
from motor.motor_asyncio import AsyncIOMotorClient

from app.api.health import router as health_router
from app.core.config import get_settings
from app.models.schemas import (
    AnswerTrace,
    EmergencyContact,
    HealthFacility,
    InboundMessage,
    LogEntry,
    UserProfile,
)

logger = logging.getLogger("lafiya.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Gestionnaire de cycle de vie (démarrage et arrêt)."""
    settings = get_settings()
    logger.info("Démarrage de Lafiya Web API (env: %s)...", settings.ENVIRONMENT)

    # Initialisation MongoDB + Beanie
    mongo_client = AsyncIOMotorClient(settings.MONGODB_URI)
    db = mongo_client[settings.MONGODB_DB]
    await init_beanie(
        database=cast(Any, db),
        document_models=[
            LogEntry,
            InboundMessage,
            UserProfile,
            HealthFacility,
            EmergencyContact,
            AnswerTrace,
        ],
    )
    logger.info("MongoDB & ODM Beanie initialisés avec succès.")

    yield

    # Arrêt propre
    mongo_client.close()
    logger.info("Arrêt de Lafiya Web API : connexions fermées.")


settings = get_settings()

app = FastAPI(
    title="Lafiya Agent IA",
    description=(
        "Assistant WhatsApp d'information et d'orientation sur le diabète et l'hypertension"
    ),
    version="0.1.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)

# Inclusion des routeurs
app.include_router(health_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Point d'accueil par défaut de l'API."""
    return {
        "app": "Lafiya Agent IA",
        "status": "running",
        "description": "Prévention et information sur le diabète et l'hypertension artérielle",
    }
