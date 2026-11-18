"""Extraction du texte brut des guides officiels PDF du corpus Lafiya.

Stratégie d'extraction (par ordre de priorité) :
  1. pdfplumber : meilleure gestion du layout et des tableaux.
  2. pypdf      : fallback si pdfplumber retourne < MIN_CHARS caractères.
  3. Skip       : si les deux échouent → log WARNING (PDF scanné probable).

Conformité CDC §6.1 : seuls les PDF listés dans PDF_SOURCES (sources officielles
OMS/IDF) sont traités. Les métadonnées sont préservées depuis le catalogue.
"""

import logging
from dataclasses import dataclass
from pathlib import Path

import pdfplumber
from pypdf import PdfReader

from scripts.ingest.sources import PDF_SOURCES, PdfSourceEntry

logger = logging.getLogger("lafiya.pdf_extractor")

# Seuil minimal de caractères pour considérer l'extraction valide
MIN_CHARS = 500

# Dossiers de référence (relatifs à la racine du projet)
_HERE = Path(__file__).resolve()
PROJECT_ROOT = _HERE.parents[2]
PDF_DIR = PROJECT_ROOT / "data" / "pdf"
EXTRACTED_DIR = PROJECT_ROOT / "data" / "extracted"


@dataclass
class ExtractedDocument:
    """Document PDF dont le texte a été extrait, prêt pour le chunking."""

    filename: str
    title: str
    source_url: str
    topic: str
    language: str
    doc_type: str  # toujours "pdf"
    text: str
    char_count: int
    extraction_method: str  # "pdfplumber" | "pypdf" | "failed"


def _extract_with_pdfplumber(pdf_path: Path) -> str:
    """Extrait le texte page par page via pdfplumber."""
    pages: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if page_text:
                pages.append(page_text.strip())
    return "\n\n".join(pages)


def _extract_with_pypdf(pdf_path: Path) -> str:
    """Extrait le texte page par page via pypdf (fallback)."""
    reader = PdfReader(str(pdf_path))
    pages: list[str] = []
    for page in reader.pages:
        page_text = page.extract_text()
        if page_text:
            pages.append(page_text.strip())
    return "\n\n".join(pages)


def _build_source_url(entry: PdfSourceEntry) -> str:
    """Reconstruit l'URL canonique IRIS depuis le handle ou l'URL directe."""
    if entry.direct_url:
        return entry.direct_url
    if entry.handle:
        return f"https://iris.who.int/handle/{entry.handle}"
    return f"data/pdf/{entry.filename}"


def extract_pdf(entry: PdfSourceEntry) -> ExtractedDocument | None:
    """Extrait le texte d'un seul PDF à partir de son entrée catalogue.

    Returns:
        ExtractedDocument si l'extraction réussit, None si le fichier est absent.
    """
    pdf_path = PDF_DIR / entry.filename

    if not pdf_path.exists():
        logger.warning("PDF introuvable : %s — ignoré", entry.filename)
        return None

    source_url = _build_source_url(entry)

    # Tentative 1 : pdfplumber
    try:
        text = _extract_with_pdfplumber(pdf_path)
        method = "pdfplumber"
    except Exception as exc:
        logger.warning("pdfplumber KO pour %s : %s", entry.filename, exc)
        text = ""
        method = "failed"

    # Fallback : pypdf
    if len(text) < MIN_CHARS:
        try:
            fallback = _extract_with_pypdf(pdf_path)
            if len(fallback) > len(text):
                text = fallback
                method = "pypdf"
        except Exception as exc:
            logger.warning("pypdf KO pour %s : %s", entry.filename, exc)

    char_count = len(text)

    if char_count < MIN_CHARS:
        logger.warning(
            "Extraction insuffisante pour %s (%d chars) — PDF scanné probable ?",
            entry.filename,
            char_count,
        )
        method = "failed"

    return ExtractedDocument(
        filename=entry.filename,
        title=entry.description,
        source_url=source_url,
        topic=entry.topic,
        language=entry.language,
        doc_type="pdf",
        text=text,
        char_count=char_count,
        extraction_method=method,
    )


def extract_all_pdfs(save_to_disk: bool = True) -> list[ExtractedDocument]:
    """Extrait le texte de tous les PDFs listés dans PDF_SOURCES.

    Args:
        save_to_disk: Si True, sauvegarde chaque texte extrait dans data/extracted/.

    Returns:
        Liste des ExtractedDocument réussis (char_count >= MIN_CHARS).
    """
    EXTRACTED_DIR.mkdir(parents=True, exist_ok=True)

    results: list[ExtractedDocument] = []
    total = len(PDF_SOURCES)
    ok = 0
    failed = 0

    logger.info("Extraction de %d PDFs → %s", total, PDF_DIR)

    for i, entry in enumerate(PDF_SOURCES, start=1):
        logger.info(
            "[%d/%d] %s",
            i,
            total,
            entry.filename[:70],
        )
        doc = extract_pdf(entry)

        if doc is None:
            failed += 1
            continue

        if doc.extraction_method == "failed":
            failed += 1
            # On ajoute quand même pour signalement, mais sans indexer
            logger.error("  ÉCHEC extraction : %s (%d chars)", doc.filename, doc.char_count)
            continue

        ok += 1
        results.append(doc)

        logger.info(
            "  ✓ %s via %s — %d chars",
            doc.filename[:60],
            doc.extraction_method,
            doc.char_count,
        )

        # Sauvegarde texte brut
        if save_to_disk:
            stem = Path(entry.filename).stem
            txt_path = EXTRACTED_DIR / f"{stem}.txt"
            txt_path.write_text(doc.text, encoding="utf-8")

    logger.info(
        "Extraction terminée : %d/%d PDFs OK, %d échecs",
        ok,
        total,
        failed,
    )
    return results
