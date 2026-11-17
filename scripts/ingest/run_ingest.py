"""Orchestrateur principal du pipeline d'ingestion RAG.

Exécution :
    .venv\\Scripts\\python.exe -m scripts.ingest.run_ingest

Étapes :
    1. Scraping des sources officielles (httpx + BeautifulSoup)
    2. Découpage en chunks (512 tokens, overlap 64)
    3. Embedding (OpenAI text-embedding-3-small)
    4. Indexation dans Qdrant Cloud (collection lafiya_corpus_who)

Conformité CDC §6.1, §6.3, §6.4 : contenus de prévention uniquement,
pas de génération de texte médical, sources officielles vérifiées.
"""

import dataclasses
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

# --- Bootstrap : ajouter la racine du projet au PYTHONPATH ---
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.core.config import get_settings  # noqa: E402
from scripts.ingest.chunker import chunk_documents  # noqa: E402
from scripts.ingest.embedder import embed_chunks  # noqa: E402
from scripts.ingest.scraper import scrape_sources  # noqa: E402
from scripts.ingest.sources import SOURCES  # noqa: E402
from scripts.ingest.upsert import upsert_embeddings  # noqa: E402

# Configuration du logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("lafiya.ingest")


def main() -> None:
    settings = get_settings()
    started_at = datetime.now(UTC)
    logger.info("=== Démarrage du pipeline d'ingestion RAG ===")
    logger.info("Collection cible : %s", settings.QDRANT_COLLECTION)
    logger.info("Sources à scraper : %d URLs", len(SOURCES))

    # Étape 1 — Scraping
    logger.info("\n--- Étape 1 : Scraping ---")
    documents = scrape_sources(SOURCES, delay_seconds=1.5)
    logger.info("Documents récupérés : %d/%d", len(documents), len(SOURCES))

    if not documents:
        logger.error("Aucun document scrapé. Pipeline interrompu.")
        sys.exit(1)

    # Sauvegarde des documents bruts pour validation humaine
    raw_docs_path = PROJECT_ROOT / "scripts" / "ingest" / "scraped_docs.json"
    raw_docs_path.write_text(
        json.dumps(
            [dataclasses.asdict(d) for d in documents],
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    logger.info("Documents bruts sauvegardés : %s", raw_docs_path)
    logger.info(
        "Validez le contenu avant de continuer (--skip-scrape pour relancer sans rescraper)."
    )

    # Étape 2 — Chunking
    logger.info("\n--- Étape 2 : Chunking ---")
    chunks = chunk_documents(documents)
    logger.info("Chunks produits : %d", len(chunks))

    if not chunks:
        logger.error("Aucun chunk produit. Pipeline interrompu.")
        sys.exit(1)

    # Étape 3 — Embedding
    logger.info("\n--- Étape 3 : Embedding ---")
    embedded = embed_chunks(chunks, api_key=settings.OPENAI_API_KEY)
    logger.info("Vecteurs générés : %d/%d", len(embedded), len(chunks))

    if not embedded:
        logger.error("Aucun vecteur généré. Pipeline interrompu.")
        sys.exit(1)

    # Étape 4 — Upsert Qdrant
    logger.info("\n--- Étape 4 : Indexation Qdrant ---")
    upserted = upsert_embeddings(
        embedded,
        qdrant_url=settings.QDRANT_URL,
        qdrant_api_key=settings.QDRANT_API_KEY,
        collection_name=settings.QDRANT_COLLECTION,
    )

    # Rapport final
    elapsed = (datetime.now(UTC) - started_at).total_seconds()
    report = {
        "started_at": started_at.isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "sources_attempted": len(SOURCES),
        "documents_scraped": len(documents),
        "chunks_produced": len(chunks),
        "vectors_generated": len(embedded),
        "points_upserted": upserted,
        "collection": settings.QDRANT_COLLECTION,
    }

    # Sauvegarde du rapport
    report_path = PROJECT_ROOT / "scripts" / "ingest" / "last_ingest_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("\n=== Pipeline terminé en %.1f secondes ===", elapsed)
    logger.info("Sources tentées  : %d", report["sources_attempted"])
    logger.info("Documents OK     : %d", report["documents_scraped"])
    logger.info("Chunks           : %d", report["chunks_produced"])
    logger.info("Vecteurs         : %d", report["vectors_generated"])
    logger.info("Points Qdrant    : %d", report["points_upserted"])
    logger.info("Rapport sauvegardé : %s", report_path)


if __name__ == "__main__":
    main()
