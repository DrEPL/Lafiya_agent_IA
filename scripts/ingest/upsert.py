"""Indexation des vecteurs dans Qdrant Cloud.

Crée la collection si elle n'existe pas (1536 dims, cosinus).
Upsert par lots de 100 points — idempotent grâce aux IDs uuid5.
Conformité CDC §6.3 : collection unique lafiya_corpus_who.
"""

import logging

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from scripts.ingest.chunker import TextChunk

logger = logging.getLogger("lafiya.upsert")

VECTOR_SIZE = 1536
BATCH_SIZE = 100


def _ensure_collection(client: QdrantClient, collection_name: str) -> None:
    """Crée la collection si elle n'existe pas encore."""
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        logger.info("Collection '%s' déjà existante.", collection_name)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )
    logger.info("Collection '%s' créée (%d dims, cosinus).", collection_name, VECTOR_SIZE)


def upsert_embeddings(
    embedded: list[tuple[TextChunk, list[float]]],
    qdrant_url: str,
    qdrant_api_key: str,
    collection_name: str,
) -> int:
    """Indexe les vecteurs dans Qdrant.

    Args:
        embedded: Paires (chunk, vecteur) issues de l'embedder.
        qdrant_url: URL du cluster Qdrant Cloud.
        qdrant_api_key: Clé API Qdrant.
        collection_name: Nom de la collection cible.

    Returns:
        Nombre de points effectivement upsertés.
    """
    client = QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=30)
    _ensure_collection(client, collection_name)

    total_upserted = 0
    total_batches = (len(embedded) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(0, len(embedded), BATCH_SIZE):
        batch = embedded[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1

        points = [
            PointStruct(
                id=chunk.chunk_id,
                vector=vector,
                payload={
                    "source": chunk.source,
                    "url": chunk.url,
                    "title": chunk.title,
                    "language": chunk.language,
                    "topic": chunk.topic,
                    "chunk_index": chunk.chunk_index,
                    "token_count": chunk.token_count,
                    "text": chunk.text,
                    "scraped_at": chunk.scraped_at,
                },
            )
            for chunk, vector in batch
        ]

        client.upsert(collection_name=collection_name, points=points, wait=True)
        total_upserted += len(points)
        logger.info(
            "Upsert batch %d/%d — %d points (total : %d)",
            batch_num,
            total_batches,
            len(points),
            total_upserted,
        )

    logger.info("Indexation terminée : %d points dans '%s'.", total_upserted, collection_name)
    return total_upserted
