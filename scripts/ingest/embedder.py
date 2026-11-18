"""Génération des embeddings via Ollama (dev local) ou OpenAI (prod).

Le provider actif est contrôlé par la variable d'environnement :
    EMBEDDING_PROVIDER=ollama   → nomic-embed-text (768 dims) — GRATUIT, local
    EMBEDDING_PROVIDER=openai   → text-embedding-3-small (512 dims) — PAYANT, prod

Traitement par lots (batch) avec retry automatique sur erreurs transitoires.
Conformité CDC §6.4 : embeddings déterministes, sources officielles uniquement.
"""

import logging
import os
import time

from scripts.ingest.chunker import TextChunk

logger = logging.getLogger("lafiya.embedder")

# --- Configuration provider ---
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "ollama")

# Ollama (dev local)
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
OLLAMA_EMBED_MODEL = os.getenv("OLLAMA_EMBED_MODEL", "nomic-embed-text")
OLLAMA_VECTOR_SIZE = 768

# OpenAI (prod)
OPENAI_EMBED_MODEL = os.getenv("OPENAI_EMBED_MODEL", "text-embedding-3-small")
OPENAI_VECTOR_SIZE = 512

BATCH_SIZE = 32  # Taille de lot (conservatif pour Ollama)
MAX_RETRIES = 5
INITIAL_BACKOFF = 2.0  # secondes


def get_vector_size() -> int:
    """Retourne la taille du vecteur selon le provider actif."""
    return OLLAMA_VECTOR_SIZE if EMBEDDING_PROVIDER == "ollama" else OPENAI_VECTOR_SIZE


# ------------------------------------------------------------------ Ollama


def _embed_ollama(texts: list[str]) -> list[list[float]]:
    """Embedding via Ollama (HTTP local — aucun coût)."""
    import ollama  # import local pour éviter l'import si provider = openai

    client = ollama.Client(host=OLLAMA_BASE_URL)
    vectors: list[list[float]] = []
    for text in texts:
        resp = client.embeddings(model=OLLAMA_EMBED_MODEL, prompt=text)
        vectors.append(resp["embedding"])
    return vectors


# ------------------------------------------------------------------ OpenAI


def _embed_openai(texts: list[str], api_key: str) -> list[list[float]]:
    """Embedding via OpenAI text-embedding-3-small (prod)."""
    from openai import OpenAI  # import local pour éviter l'import si provider = ollama

    client = OpenAI(api_key=api_key)
    response = client.embeddings.create(
        model=OPENAI_EMBED_MODEL,
        input=texts,
        dimensions=OPENAI_VECTOR_SIZE,
    )
    return [obj.embedding for obj in response.data]


# ------------------------------------------------------------------ Public API


def embed_chunks(
    chunks: list[TextChunk],
    api_key: str = "",
) -> list[tuple[TextChunk, list[float]]]:
    """Génère les embeddings pour une liste de chunks.

    Args:
        chunks:  Chunks à embedder (sortie de chunker.py).
        api_key: Clé OpenAI (ignorée si EMBEDDING_PROVIDER=ollama).

    Returns:
        Liste de tuples (chunk, vecteur). Les chunks en erreur sont ignorés.
    """
    provider = EMBEDDING_PROVIDER
    logger.info(
        "Provider embedding : %s — modèle : %s",
        provider,
        OLLAMA_EMBED_MODEL if provider == "ollama" else OPENAI_EMBED_MODEL,
    )

    if provider == "openai" and not api_key:
        logger.error(
            "OPENAI_API_KEY manquant — passez EMBEDDING_PROVIDER=ollama pour le dev local."
        )
        return []

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
                if provider == "ollama":
                    vectors = _embed_ollama(texts)
                else:
                    vectors = _embed_openai(texts, api_key)

                for chunk, vector in zip(batch, vectors, strict=True):
                    results.append((chunk, vector))
                logger.info("  Batch %d OK — %d vecteurs", batch_num, len(batch))
                break

            except Exception as exc:
                # Détection erreur définitive OpenAI (401)
                exc_str = str(exc)
                if "AuthenticationError" in type(exc).__name__ or "401" in exc_str:
                    logger.error("  Clé API invalide (401) — vérifiez OPENAI_API_KEY dans .env")
                    return results

                if attempt == MAX_RETRIES:
                    logger.error(
                        "  Batch %d abandonné après %d tentatives : %s",
                        batch_num,
                        MAX_RETRIES,
                        exc,
                    )
                    break

                logger.warning(
                    "  Erreur (%s) — attente %.1fs (tentative %d/%d)",
                    exc,
                    backoff,
                    attempt,
                    MAX_RETRIES,
                )
                time.sleep(backoff)
                backoff = min(backoff * 2, 60.0)

    logger.info("Embedding terminé : %d/%d chunks vectorisés", len(results), len(chunks))
    return results
