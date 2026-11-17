"""Génération des embeddings via OpenAI text-embedding-3-small.

Traitement par lots de 100 textes (limite recommandée OpenAI).
Retry automatique sur les erreurs transitoires (RateLimitError, APIError).
Conformité CDC §6.4 : modèle text-embedding-3-small, 1536 dimensions.
"""

import logging
import time

from openai import APIError, AuthenticationError, OpenAI, RateLimitError

from scripts.ingest.chunker import TextChunk

logger = logging.getLogger("lafiya.embedder")

EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
BATCH_SIZE = 100
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # secondes


def embed_chunks(
    chunks: list[TextChunk],
    api_key: str,
) -> list[tuple[TextChunk, list[float]]]:
    """Génère les embeddings pour une liste de chunks.

    Args:
        chunks: Chunks à embedder.
        api_key: Clé OpenAI.

    Returns:
        Liste de tuples (chunk, vecteur). Les chunks en erreur sont ignorés.
    """
    client = OpenAI(api_key=api_key)
    results: list[tuple[TextChunk, list[float]]] = []
    total_batches = (len(chunks) + BATCH_SIZE - 1) // BATCH_SIZE

    for batch_idx in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[batch_idx : batch_idx + BATCH_SIZE]
        batch_num = batch_idx // BATCH_SIZE + 1
        logger.info("Embedding batch %d/%d (%d chunks)...", batch_num, total_batches, len(batch))

        texts = [c.text for c in batch]
        backoff = INITIAL_BACKOFF

        for attempt in range(1, MAX_RETRIES + 1):
            try:
                response = client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=texts,
                    dimensions=EMBEDDING_DIMENSIONS,
                )
                for chunk, embedding_obj in zip(batch, response.data, strict=True):
                    results.append((chunk, embedding_obj.embedding))
                logger.info("  Batch %d OK — %d vecteurs", batch_num, len(batch))
                break

            except AuthenticationError as exc:
                # 401 : erreur définitive, inutile de retenter
                logger.error("  Batch %d abandonné — clé API invalide : %s", batch_num, exc)
                logger.error("  Vérifiez OPENAI_API_KEY dans votre .env et relancez.")
                return results  # arrêt immédiat du pipeline embedding

            except RateLimitError:
                if attempt == MAX_RETRIES:
                    logger.error("  Batch %d abandonné — quota épuisé.", batch_num)
                    break
                logger.warning(
                    "  Rate limit — attente %.1fs (tentative %d/%d)",
                    backoff,
                    attempt,
                    MAX_RETRIES,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

            except APIError as exc:
                if attempt == MAX_RETRIES:
                    logger.error("  Batch %d abandonné — %s", batch_num, exc)
                    break
                logger.warning(
                    "  Erreur API (%s) — tentative %d/%d",
                    exc,
                    attempt,
                    MAX_RETRIES,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    logger.info("Embedding terminé : %d/%d chunks vectorisés", len(results), len(chunks))
    return results
