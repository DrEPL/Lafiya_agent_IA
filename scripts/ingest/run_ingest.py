"""Orchestrateur principal du pipeline d'ingestion RAG Lafiya.

Exécution :
    .venv\\Scripts\\python.exe -m scripts.ingest.run_ingest [OPTIONS]

Étapes :
    1. Scraping des 11 sources web officielles (httpx + BeautifulSoup)
    2. Extraction du texte des 30 PDF OMS (pdfplumber → pypdf fallback)
    3. Découpage en chunks (512 tokens, overlap 64, préservation paragraphes)
    4. Embedding (Ollama nomic-embed-text en dev / OpenAI text-embedding-3-small en prod)
    5. Indexation dans Qdrant (local Docker en dev / Qdrant Cloud en prod)

Options CLI :
    --web-only      Traite uniquement les sources web (pas les PDF)
    --pdf-only      Traite uniquement les PDF (pas les sources web)
    --skip-scrape   Charge scraped_docs.json existant (évite le re-scraping)
    --skip-extract  Charge extracted_docs.json existant (évite la re-extraction PDF)
    --dry-run       Arrête avant l'embedding (chunking uniquement)

Conformité CDC §6.1, §6.3, §6.4 : contenus de prévention uniquement,
pas de génération de texte médical, sources officielles vérifiées.
"""

import argparse
import dataclasses
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

# --- Bootstrap : ajouter la racine du projet au PYTHONPATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ingest.chunker import (  # noqa: E402
    TextChunk,
    chunk_documents,
    chunk_pdf_documents,
)
from scripts.ingest.embedder import embed_chunks  # noqa: E402
from scripts.ingest.pdf_extractor import ExtractedDocument, extract_all_pdfs  # noqa: E402
from scripts.ingest.scraper import ScrapedDocument, scrape_sources  # noqa: E402
from scripts.ingest.sources import SOURCES  # noqa: E402
from scripts.ingest.upsert import upsert_embeddings  # noqa: E402

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lafiya.ingest")

SCRAPED_DOCS_PATH = PROJECT_ROOT / "scripts" / "ingest" / "scraped_docs.json"
EXTRACTED_DOCS_PATH = PROJECT_ROOT / "scripts" / "ingest" / "extracted_docs.json"
REPORT_PATH = PROJECT_ROOT / "scripts" / "ingest" / "last_ingest_report.json"


# ------------------------------------------------------------------ Helpers


def _load_scraped_docs() -> list[ScrapedDocument]:
    """Charge scraped_docs.json depuis le disque."""
    if not SCRAPED_DOCS_PATH.exists():
        logger.error("Fichier introuvable : %s — lancez sans --skip-scrape", SCRAPED_DOCS_PATH)
        sys.exit(1)
    raw = json.loads(SCRAPED_DOCS_PATH.read_text(encoding="utf-8"))
    return [ScrapedDocument(**d) for d in raw]


def _save_scraped_docs(docs: list[ScrapedDocument]) -> None:
    SCRAPED_DOCS_PATH.write_text(
        json.dumps([dataclasses.asdict(d) for d in docs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Documents web sauvegardés : %s", SCRAPED_DOCS_PATH)


def _save_extracted_docs(docs: list[ExtractedDocument]) -> None:
    EXTRACTED_DOCS_PATH.write_text(
        json.dumps([dataclasses.asdict(d) for d in docs], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info("Documents PDF sauvegardés : %s", EXTRACTED_DOCS_PATH)


def _load_extracted_docs() -> list[ExtractedDocument]:
    """Charge extracted_docs.json depuis le disque."""
    if not EXTRACTED_DOCS_PATH.exists():
        logger.error("Fichier introuvable : %s — lancez sans --skip-extract", EXTRACTED_DOCS_PATH)
        sys.exit(1)
    raw = json.loads(EXTRACTED_DOCS_PATH.read_text(encoding="utf-8"))
    return [ExtractedDocument(**d) for d in raw]


# ------------------------------------------------------------------ Main


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Pipeline d'ingestion RAG Lafiya (web + PDF → Qdrant)"
    )
    parser.add_argument("--web-only", action="store_true", help="Traite uniquement les sources web")
    parser.add_argument("--pdf-only", action="store_true", help="Traite uniquement les PDF")
    parser.add_argument(
        "--skip-scrape",
        action="store_true",
        help="Charge scraped_docs.json existant sans re-scraper",
    )
    parser.add_argument(
        "--skip-extract",
        action="store_true",
        help="Charge extracted_docs.json existant sans re-extraire les PDF",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Arrête avant l'embedding (chunking uniquement)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    started_at = datetime.now(UTC)

    # Lecture de la configuration depuis .env (via variables d'environnement)
    openai_api_key = os.getenv("OPENAI_API_KEY", "")
    embedding_provider = os.getenv("EMBEDDING_PROVIDER", "ollama")
    qdrant_url = os.getenv("QDRANT_LOCAL_URL", os.getenv("QDRANT_URL", "http://localhost:6333"))
    qdrant_api_key = os.getenv("QDRANT_API_KEY", "")
    qdrant_collection = os.getenv("QDRANT_COLLECTION", "lafiya_corpus_who")

    logger.info("=== Démarrage du pipeline d'ingestion RAG Lafiya ===")
    logger.info("Provider embedding : %s", embedding_provider)
    logger.info("Qdrant             : %s", qdrant_url)
    logger.info("Collection cible   : %s", qdrant_collection)

    all_chunks: list[TextChunk] = []
    scraped_count = 0
    pdf_count = 0
    now_iso = started_at.isoformat()

    # ---------------------------------------------------------------- Étape 1 : Web
    if not args.pdf_only:
        logger.info("\n--- Étape 1 : Sources web ---")
        if args.skip_scrape:
            logger.info("Chargement depuis %s (--skip-scrape actif)", SCRAPED_DOCS_PATH)
            web_docs = _load_scraped_docs()
        else:
            web_docs = scrape_sources(SOURCES, delay_seconds=1.5)
            _save_scraped_docs(web_docs)

        scraped_count = len(web_docs)
        logger.info("Documents web : %d/%d", scraped_count, len(SOURCES))

        if web_docs:
            logger.info("\n--- Étape 2a : Chunking web ---")
            web_chunks = chunk_documents(web_docs)
            all_chunks.extend(web_chunks)
            logger.info("Chunks web : %d", len(web_chunks))

    # ---------------------------------------------------------------- Étape 2 : PDF
    if not args.web_only:
        logger.info("\n--- Étape 1b : Extraction PDF ---")
        if args.skip_extract:
            logger.info("Chargement depuis %s (--skip-extract actif)", EXTRACTED_DOCS_PATH)
            pdf_docs = _load_extracted_docs()
        else:
            pdf_docs = extract_all_pdfs(save_to_disk=True)
            _save_extracted_docs(pdf_docs)

        pdf_count = len(pdf_docs)
        logger.info("PDFs extraits : %d/30", pdf_count)

        if pdf_docs:
            logger.info("\n--- Étape 2b : Chunking PDF ---")
            pdf_chunks = chunk_pdf_documents(pdf_docs, scraped_at=now_iso)
            all_chunks.extend(pdf_chunks)
            logger.info("Chunks PDF : %d", len(pdf_chunks))

    # ---------------------------------------------------------------- Bilan chunking
    logger.info("\n--- Bilan chunking ---")
    logger.info("Total chunks : %d (web + PDF)", len(all_chunks))

    if not all_chunks:
        logger.error("Aucun chunk produit. Pipeline interrompu.")
        sys.exit(1)

    if args.dry_run:
        logger.info("--dry-run actif : arrêt avant l'embedding.")
        return

    # ---------------------------------------------------------------- Étape 3 : Embedding
    logger.info("\n--- Étape 3 : Embedding ---")
    embedded = embed_chunks(all_chunks, api_key=openai_api_key)
    logger.info("Vecteurs générés : %d/%d", len(embedded), len(all_chunks))

    if not embedded:
        logger.error("Aucun vecteur généré. Pipeline interrompu.")
        sys.exit(1)

    # ---------------------------------------------------------------- Étape 4 : Qdrant
    logger.info("\n--- Étape 4 : Indexation Qdrant ---")
    upserted = upsert_embeddings(
        embedded,
        qdrant_url=qdrant_url,
        qdrant_api_key=qdrant_api_key,
        collection_name=qdrant_collection,
    )

    # ---------------------------------------------------------------- Rapport
    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    report = {
        "started_at": started_at.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "embedding_provider": embedding_provider,
        "qdrant_url": qdrant_url,
        "collection": qdrant_collection,
        "web_documents": scraped_count,
        "pdf_documents": pdf_count,
        "total_chunks": len(all_chunks),
        "vectors_generated": len(embedded),
        "points_upserted": upserted,
    }
    REPORT_PATH.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("\n=== Pipeline terminé en %.1f secondes ===", elapsed)
    logger.info("Provider         : %s", embedding_provider)
    logger.info("Documents web    : %d", scraped_count)
    logger.info("Documents PDF    : %d", pdf_count)
    logger.info("Chunks totaux    : %d", len(all_chunks))
    logger.info("Vecteurs         : %d", len(embedded))
    logger.info("Points Qdrant    : %d", upserted)
    logger.info("Rapport          : %s", REPORT_PATH)


if __name__ == "__main__":
    main()
