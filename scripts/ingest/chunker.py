"""Découpage des documents en chunks indexables.

Stratégie : fenêtre glissante basée sur les tokens (tiktoken).
- Taille cible : 512 tokens par chunk
- Chevauchement : 64 tokens (préserve le contexte entre chunks)
- Encodage : cl100k_base (compatible Ollama nomic-embed-text et OpenAI)

Le découpage se fait par paragraphes pour préserver la cohérence
sémantique : on ne coupe jamais au milieu d'un paragraphe.

Accepte deux types de sources :
  - ScrapedDocument  (pages web scrapées)
  - ExtractedDocument (guides PDF extraits)
"""

import logging
import uuid
from dataclasses import dataclass

import tiktoken

from scripts.ingest.pdf_extractor import ExtractedDocument
from scripts.ingest.scraper import ScrapedDocument

logger = logging.getLogger("lafiya.chunker")

ENCODING_NAME = "cl100k_base"  # compatible text-embedding-3-small et nomic-embed-text
CHUNK_SIZE_TOKENS = 512
CHUNK_OVERLAP_TOKENS = 64

_enc = tiktoken.get_encoding(ENCODING_NAME)


@dataclass
class TextChunk:
    """Chunk de texte prêt pour l'embedding."""

    chunk_id: str  # uuid5 déterministe (source_key + index)
    url: str
    source: str
    topic: str
    language: str
    title: str
    doc_type: str  # "web" | "pdf"
    text: str
    chunk_index: int
    total_chunks: int
    token_count: int
    scraped_at: str


def _count_tokens(text: str) -> int:
    return len(_enc.encode(text))


def _split_into_chunks(text: str, title: str) -> list[str]:
    """Découpe le texte en chunks à fenêtre glissante par paragraphes."""
    # Préfixe chaque chunk avec le titre pour ancrer le contexte sémantique
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


def _make_chunks_from_raw(
    raw_chunks: list[str],
    source_key: str,
    url: str,
    source: str,
    topic: str,
    language: str,
    title: str,
    doc_type: str,
    scraped_at: str,
) -> list[TextChunk]:
    """Construit des TextChunk à partir des segments bruts."""
    total = len(raw_chunks)
    result: list[TextChunk] = []
    for idx, chunk_text in enumerate(raw_chunks):
        chunk_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_key}#{idx}"))
        result.append(
            TextChunk(
                chunk_id=chunk_id,
                url=url,
                source=source,
                topic=topic,
                language=language,
                title=title,
                doc_type=doc_type,
                text=chunk_text,
                chunk_index=idx,
                total_chunks=total,
                token_count=_count_tokens(chunk_text),
                scraped_at=scraped_at,
            )
        )
    return result


def chunk_documents(documents: list[ScrapedDocument]) -> list[TextChunk]:
    """Transforme une liste de documents web scrapés en chunks prêts à l'embedding."""
    all_chunks: list[TextChunk] = []

    for doc in documents:
        raw_chunks = _split_into_chunks(doc.text, doc.title)

        if not raw_chunks:
            logger.warning("Aucun chunk produit pour : %s", doc.url)
            continue

        chunks = _make_chunks_from_raw(
            raw_chunks=raw_chunks,
            source_key=doc.url,
            url=doc.url,
            source=doc.source,
            topic=doc.topic,
            language=doc.language,
            title=doc.title,
            doc_type="web",
            scraped_at=doc.scraped_at,
        )
        all_chunks.extend(chunks)

        logger.info(
            "  [web] %s → %d chunks (moy. %d tokens)",
            doc.title[:50],
            len(raw_chunks),
            sum(_count_tokens(c) for c in raw_chunks) // max(len(raw_chunks), 1),
        )

    logger.info("Web — Total : %d chunks pour %d documents", len(all_chunks), len(documents))
    return all_chunks


def chunk_pdf_documents(
    pdf_docs: list[ExtractedDocument],
    scraped_at: str,
) -> list[TextChunk]:
    """Transforme une liste de documents PDF extraits en chunks prêts à l'embedding.

    Args:
        pdf_docs: Résultat de extract_all_pdfs().
        scraped_at: Horodatage ISO 8601 de l'exécution du pipeline.

    Returns:
        Liste de TextChunk avec doc_type="pdf".
    """
    all_chunks: list[TextChunk] = []

    for doc in pdf_docs:
        raw_chunks = _split_into_chunks(doc.text, doc.title)

        if not raw_chunks:
            logger.warning("Aucun chunk produit pour PDF : %s", doc.filename)
            continue

        chunks = _make_chunks_from_raw(
            raw_chunks=raw_chunks,
            source_key=doc.source_url,
            url=doc.source_url,
            source="who_pdf",
            topic=doc.topic,
            language=doc.language,
            title=doc.title,
            doc_type="pdf",
            scraped_at=scraped_at,
        )
        all_chunks.extend(chunks)

        logger.info(
            "  [pdf] %s → %d chunks (moy. %d tokens)",
            doc.filename[:55],
            len(raw_chunks),
            sum(_count_tokens(c) for c in raw_chunks) // max(len(raw_chunks), 1),
        )

    logger.info("PDF — Total : %d chunks pour %d documents", len(all_chunks), len(pdf_docs))
    return all_chunks
