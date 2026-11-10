"""Endpoints de vérification de disponibilité et d'état de l'application.

Conformité CDC (§5.1, §9.9) :
- GET /health : liveness probe (disponibilité du processus FastAPI).
- GET /ready : readiness probe (contrôle de santé de Redis, MongoDB Atlas et Qdrant Cloud).
"""

from typing import Any

import redis.asyncio as aioredis
from fastapi import APIRouter, Response, status
from motor.motor_asyncio import AsyncIOMotorClient
from qdrant_client import AsyncQdrantClient

from app.core.config import get_settings

router = APIRouter(tags=["Health & Monitoring"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def liveness_check() -> dict[str, str]:
    """Liveness probe indiquant que le serveur Web FastAPI est actif."""
    return {"status": "ok", "service": "lafiya-web"}


@router.get("/ready")
async def readiness_check(response: Response) -> dict[str, Any]:
    """Readiness probe vérifiant les dépendances (Redis, MongoDB, Qdrant)."""
    settings = get_settings()
    checks: dict[str, str] = {}
    is_ready = True

    # 1. Vérification Redis
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_timeout=2.0)
        await r.ping()
        await r.aclose()
        checks["redis"] = "ok"
    except Exception as e:
        checks["redis"] = f"error: {e}"
        is_ready = False

    # 2. Vérification MongoDB Atlas
    try:
        m = AsyncIOMotorClient(settings.MONGODB_URI, serverSelectionTimeoutMS=2000)
        db = m[settings.MONGODB_DB]
        await db.command("ping")
        m.close()
        checks["mongodb"] = "ok"
    except Exception as e:
        checks["mongodb"] = f"error: {e}"
        is_ready = False

    # 3. Vérification Qdrant Cloud
    try:
        q = AsyncQdrantClient(url=settings.QDRANT_URL, api_key=settings.QDRANT_API_KEY, timeout=3)
        await q.get_collections()
        await q.close()
        checks["qdrant"] = "ok"
    except Exception as e:
        checks["qdrant"] = f"error: {e}"
        is_ready = False

    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "dependencies": checks,
    }
