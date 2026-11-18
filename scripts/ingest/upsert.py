"""Indexation des vecteurs dans Qdrant (local ou Cloud).

Crée la collection si elle n'existe pas.
Taille des vecteurs adaptée au provider actif :
    EMBEDDING_PROVIDER=ollama  → 768 dims (nomic-embed-text)
    EMBEDDING_PROVIDER=openai  → 512 dims (text-embedding-3-small)

Upsert par lots de 100 points — idempotent grâce aux IDs uuid5.
Conformité CDC §6.3 : collection unique lafiya_corpus_who.
"""

import logging
import os

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    PointStruct,
    VectorParams,
)

from scripts.ingest.chunker import TextChunk
from scripts.ingest.embedder import get_vector_size

logger = logging.getLogger("lafiya.upsert")

BATCH_SIZE = 100

# Payload additionnel pour traçabilité
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")


def _build_client(qdrant_url: str, qdrant_api_key: str) -> QdrantClient:
    """Construit le client Qdrant (local ou Cloud selon l'URL)."""
    is_local = "localhost" in qdrant_url or "127.0.0.1" in qdrant_url
    if is_local:
        # Connexion locale — pas besoin de clé API
        return QdrantClient(url=qdrant_url, timeout=30)
    return QdrantClient(url=qdrant_url, api_key=qdrant_api_key, timeout=30)


def _ensure_collection(
    client: QdrantClient,
    collection_name: str,
    vector_size: int,
) -> None:
    """Crée la collection si elle n'existe pas.

    Si elle existe avec une taille différente, lève une ValueError
    pour forcer une recréation manuelle (sécurité anti-corruption).
    """
    existing = {c.name for c in client.get_collections().collections}
    if collection_name in existing:
        # Vérifier la cohérence des dimensions
        info = client.get_collection(collection_name)
        vectors_cfg = info.config.params.vectors
        if isinstance(vectors_cfg, dict):
            # Multi-vecteurs : on vérifie le premier
            existing_size = next(iter(vectors_cfg.values())).size
        elif vectors_cfg is not None:
            existing_size = vectors_cfg.size  # type: ignore[union-attr]
        else:
            existing_size = 0
        if existing_size != vector_size:
            raise ValueError(
                f"Collection '{collection_name}' existe avec {existing_size} dims "
                f"mais le provider actuel requiert {vector_size} dims. "
                "Supprimez la collection manuellement (Qdrant Dashboard) et relancez."
            )
        logger.info("Collection '%s' déjà existante (%d dims).", collection_name, existing_size)
        return

    client.create_collection(
        collection_name=collection_name,
        vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
    )
    logger.info(
        "Collection '%s' créée (%d dims, cosinus, provider=%s).",
        collection_name,
        vector_size,
        EMBEDDING_PROVIDER,
    )


def upsert_embeddings(
    embedded: list[tuple[TextChunk, list[float]]],
    qdrant_url: str,
    qdrant_api_key: str,
    collection_name: str,
) -> int:
    """Indexe les vecteurs dans Qdrant.

    Args:
        embedded:        Paires (chunk, vecteur) issues de l'embedder.
        qdrant_url:      URL du serveur Qdrant (local ou Cloud).
        qdrant_api_key:  Clé API Qdrant (vide pour usage local).
        collection_name: Nom de la collection cible.

    Returns:
        Nombre de points effectivement upsertés.
    """
    vector_size = get_vector_size()
    client = _build_client(qdrant_url, qdrant_api_key)
    _ensure_collection(client, collection_name, vector_size)

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
                    "doc_type": chunk.doc_type,
                    "chunk_index": chunk.chunk_index,
                    "total_chunks": chunk.total_chunks,
                    "token_count": chunk.token_count,
                    "text": chunk.text,
                    "scraped_at": chunk.scraped_at,
                    "embedding_provider": EMBEDDING_PROVIDER,
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
