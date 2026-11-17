"""Découpage des documents en chunks indexables.

Stratégie : fenêtre glissante basée sur les tokens (tiktoken).
- Taille cible : 512 tokens par chunk
- Chevauchement : 64 tokens (préserve le contexte entre chunks)
- Encodage : cl100k_base (utilisé par text-embedding-3-small)

Le découpage se fait par paragraphes pour préserver la cohérence
sémantique : on ne coupe jamais au milieu d'un paragraphe.
"""

import logging
import uuid
from dataclasses import dataclass

import tiktoken

from scripts.ingest.scraper import ScrapedDocument

logger = logging.getLogger("lafiya.chunker")

ENCODING_NAME = "cl100k_base"  # compatible text-embedding-3-small
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

_enc = tiktoken.get_encoding(ENCODING_NAME)


@dataclass
class TextChunk:
    """Chunk de texte prêt pour l'embedding."""

    chunk_id: str  # uuid5 déterministe (url + index)
    url: str
    source: str
    topic: str
    language: str
    title: str
    text: str
    chunk_index: int
    token_count: int
    scraped_at: str


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_into_chunks(text: str, title: str) -> list[str]:
    """Découpe le texte en chunks à fenêtre glissante par paragraphes."""
    # On préfixe chaque chunk avec le titre pour ancrer le contexte sémantique
    title_prefix = f"{title}\n\n"
    title_tokens = _count_tokens(title_prefix)
    effective_size = CHUNK_SIZE_TOKENS - title_tokens

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    chunks: list[str] = []
    current_tokens: list[int] = []  # token ids du chunk courant
    overlap_buffer: list[int] = []  # tokens de chevauchement pour le prochain chunk

    for para in paragraphs:
        para_tokens = _enc.encode(para)

        # Si le paragraphe seul dépasse effective_size, on le découpe brutalement
        if len(para_tokens) > effective_size:
            # Vider le chunk courant d'abord
            if current_tokens:
                chunk_text = title_prefix + _enc.decode(current_tokens)
                chunks.append(chunk_text)
                overlap_buffer = current_tokens[-CHUNK_OVERLAP_TOKENS:]
                current_tokens = list(overlap_buffer)

            # Découpe forcée du paragraphe trop long
            for i in range(0, len(para_tokens), effective_size - CHUNK_OVERLAP_TOKENS):
                slice_tokens = para_tokens[i : i + effective_size]
                chunk_text = title_prefix + _enc.decode(slice_tokens)
                chunks.append(chunk_text)

            overlap_buffer = para_tokens[-CHUNK_OVERLAP_TOKENS:]
            current_tokens = list(overlap_buffer)
            continue

        # Le paragraphe tient dans le chunk courant
        if len(current_tokens) + len(para_tokens) + 1 <= effective_size:
            if current_tokens:
                current_tokens.append(_enc.encode("\n\n")[0])  # séparateur
            current_tokens.extend(para_tokens)
        else:
            # Fermer le chunk courant
            if current_tokens:
                chunk_text = title_prefix + _enc.decode(current_tokens)
                chunks.append(chunk_text)
                overlap_buffer = current_tokens[-CHUNK_OVERLAP_TOKENS:]
            # Ouvrir le nouveau chunk avec l'overlap + ce paragraphe
            current_tokens = list(overlap_buffer) + list(para_tokens)

    # Dernier chunk
    if current_tokens:
        chunk_text = title_prefix + _enc.decode(current_tokens)
        chunks.append(chunk_text)

    return chunks


def chunk_documents(documents: list[ScrapedDocument]) -> list[TextChunk]:
    """Transforme une liste de documents scrapés en chunks prêts à l'embedding."""
    all_chunks: list[TextChunk] = []

    for doc in documents:
        raw_chunks = _split_into_chunks(doc.text, doc.title)

        if not raw_chunks:
            logger.warning("Aucun chunk produit pour : %s", doc.url)
            continue

        for idx, chunk_text in enumerate(raw_chunks):
            # ID déterministe : même URL + même index → même ID (idempotence)
            chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{doc.url}#{idx}"))
            token_count = _count_tokens(chunk_text)

            all_chunks.append(
                TextChunk(
                    chunk_id=chunk_id,
                    url=doc.url,
                    source=doc.source,
                    topic=doc.topic,
                    language=doc.language,
                    title=doc.title,
                    text=chunk_text,
                    chunk_index=idx,
                    token_count=token_count,
                    scraped_at=doc.scraped_at,
                )
            )

        logger.info(
            "  %s → %d chunks (moy. %d tokens)",
            doc.title[:50],
            len(raw_chunks),
            sum(_count_tokens(c) for c in raw_chunks) // max(len(raw_chunks), 1),
        )

    logger.info("Total : %d chunks pour %d documents", len(all_chunks), len(documents))
    return all_chunks
