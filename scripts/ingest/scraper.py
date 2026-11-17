"""Scraper HTTP robuste basé sur httpx + BeautifulSoup pour pages Web et PDF officiels.

Fonctionnalités :
1. Extraction de texte brut nettoyé depuis les pages Web officielles de santé.
2. Téléchargement direct des guides et rapports officiels en PDF (DSpace IRIS OMS & IDF).
3. Export automatique en Markdown individuel pour relecture humaine.

Conformité CDC §3.2 : aucun contenu inventé, sources officielles strictes.
"""

import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx
from bs4 import BeautifulSoup

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.ingest.sources import PDF_SOURCES, SOURCES, PdfSourceEntry, SourceEntry  # noqa: E402

logger = logging.getLogger("lafiya.scraper")

_GENERIC_SELECTORS = [
    "main",
    "article",
    '[role="main"]',
    "#content",
    ".content",
    "#main-content",
    ".main-content",
    "div.entry-content",
    "div.page-content",
]

_STRIP_TAGS = {
    "script",
    "style",
    "nav",
    "header",
    "footer",
    "aside",
    "form",
    "button",
    "noscript",
    "iframe",
    "figure",
    "figcaption",
}

_HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; LafiyaBot/1.0; +https://github.com/DrEPL/Lafiya_agent_IA)",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Accept": "text/html,application/xhtml+xml",
}


@dataclass
class ScrapedDocument:
    """Document brut extrait d'une URL."""

    url: str
    source: str
    topic: str
    language: str
    title: str
    text: str
    scraped_at: str


def _extract_text(html: str, selector: str) -> tuple[str, str]:
    soup = BeautifulSoup(html, "lxml")
    title_tag = soup.find("title")
    title = title_tag.get_text(strip=True) if title_tag else ""

    for tag in soup.find_all(_STRIP_TAGS):
        tag.decompose()

    block = None
    candidates = [selector] + _GENERIC_SELECTORS if selector else _GENERIC_SELECTORS
    for sel in candidates:
        if not sel:
            continue
        block = soup.select_one(sel)
        if block:
            break

    if block is None:
        block = soup.find("body") or soup

    paragraphs = []
    for tag in block.find_all(["p", "li", "h1", "h2", "h3", "h4", "h5", "td"]):
        text = tag.get_text(separator=" ", strip=True)
        if len(text) > 30:
            paragraphs.append(text)

    return title, "\n\n".join(paragraphs)


def scrape_sources(
    sources: list[SourceEntry],
    delay_seconds: float = 1.5,
    timeout_seconds: float = 20.0,
    max_retries: int = 3,
) -> list[ScrapedDocument]:
    """Scrape toutes les URLs web spécifiées."""
    documents: list[ScrapedDocument] = []
    total = len(sources)

    with httpx.Client(headers=_HEADERS, timeout=timeout_seconds, follow_redirects=True) as client:
        for idx, entry in enumerate(sources, 1):
            logger.info("[%d/%d] Scraping web : %s", idx, total, entry.url)

            html: str | None = None
            last_error: Exception | None = None

            for attempt in range(1, max_retries + 1):
                try:
                    response = client.get(entry.url)
                    response.raise_for_status()
                    html = response.text
                    break
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 404, 410):
                        logger.warning(
                            "  Erreur HTTP %d (définitive) : %s",
                            exc.response.status_code,
                            entry.url,
                        )
                        last_error = exc
                        break
                    last_error = exc
                    logger.warning(
                        "  Tentative %d/%d — HTTP %d : %s",
                        attempt,
                        max_retries,
                        exc.response.status_code,
                        entry.url,
                    )
                    time.sleep(delay_seconds * attempt)
                except httpx.RequestError as exc:
                    last_error = exc
                    logger.warning(
                        "  Tentative %d/%d — Erreur réseau : %s",
                        attempt,
                        max_retries,
                        exc,
                    )
                    time.sleep(delay_seconds * attempt)

            if html is None:
                logger.error("  Abandon de %s : %s", entry.url, last_error)
                time.sleep(delay_seconds)
                continue

            title, text = _extract_text(html, entry.content_selector)
            if entry.forced_title:
                title = entry.forced_title
            elif not title:
                title = entry.url

            if len(text) < 100:
                logger.warning("  Contenu trop court (%d car.) — ignoré : %s", len(text), entry.url)
                time.sleep(delay_seconds)
                continue

            documents.append(
                ScrapedDocument(
                    url=entry.url,
                    source=entry.source,
                    topic=entry.topic,
                    language=entry.language,
                    title=title,
                    text=text,
                    scraped_at=datetime.now(UTC).isoformat(),
                )
            )
            logger.info("  OK — %d caractères extraits (titre : %s)", len(text), title[:60])
            time.sleep(delay_seconds)

    return documents


def download_pdf_sources(
    pdf_sources: list[PdfSourceEntry],
    target_dir: Path | None = None,
) -> int:
    """Télécharge l'ensemble des PDF officiels dans data/pdf/."""
    pdf_dir = target_dir or (PROJECT_ROOT / "data" / "pdf")
    pdf_dir.mkdir(parents=True, exist_ok=True)

    downloaded = 0
    total = len(pdf_sources)
    logger.info("=== Téléchargement des PDF officiels (%d documents) ===", total)

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }

    with httpx.Client(headers=headers, timeout=120.0, follow_redirects=True) as client:
        for idx, entry in enumerate(pdf_sources, 1):
            dest = pdf_dir / entry.filename
            if dest.exists() and dest.stat().st_size > 50000:
                logger.info(
                    "[%d/%d] PDF déjà présent : %s (%d Ko)",
                    idx,
                    total,
                    entry.filename,
                    dest.stat().st_size // 1024,
                )
                downloaded += 1
                continue

            logger.info("[%d/%d] Téléchargement : %s...", idx, total, entry.filename)

            try:
                # Cas 1 : URL directe (ex: IDF S3)
                if entry.direct_url:
                    dl_resp = client.get(entry.direct_url)
                    if dl_resp.status_code == 200 and len(dl_resp.content) > 10000:
                        dest.write_bytes(dl_resp.content)
                        logger.info(
                            "  Succès direct : %s (%d Ko)",
                            entry.filename,
                            len(dl_resp.content) // 1024,
                        )
                        downloaded += 1
                        continue

                # Cas 2 : Handle OMS IRIS DSpace
                if entry.handle:
                    handle_url = f"https://iris.who.int/handle/{entry.handle}"
                    r_loc = httpx.get(handle_url, follow_redirects=False, timeout=20.0)
                    location = r_loc.headers.get("location", "")
                    if not location or "/items/" not in location:
                        logger.warning("  Handle non résolu : %s", entry.handle)
                        continue

                    item_uuid = location.strip("/").split("/")[-1]
                    bundles_url = f"https://iris.who.int/server/api/core/items/{item_uuid}/bundles"
                    b_resp = httpx.get(bundles_url, timeout=20.0)
                    bundles = b_resp.json().get("_embedded", {}).get("bundles", [])

                    pdf_ok = False
                    for b in bundles:
                        if b.get("name") == "ORIGINAL":
                            bs_url = b["_links"]["bitstreams"]["href"]
                            bitstreams = (
                                httpx.get(bs_url, timeout=20.0)
                                .json()
                                .get("_embedded", {})
                                .get("bitstreams", [])
                            )

                            selected_bs = None
                            for bs in bitstreams:
                                name = bs.get("name", "").lower()
                                if name.endswith(".pdf"):
                                    if "-fre" in name or "_fre" in name or "french" in name:
                                        selected_bs = bs
                                        break
                                    if selected_bs is None:
                                        selected_bs = bs

                            if selected_bs:
                                dl_url = selected_bs["_links"]["content"]["href"]
                                dl_resp = httpx.get(dl_url, follow_redirects=True, timeout=180.0)
                                if dl_resp.status_code == 200 and len(dl_resp.content) > 10000:
                                    dest.write_bytes(dl_resp.content)
                                    logger.info(
                                        "  Succès IRIS : %s (%d Ko)",
                                        entry.filename,
                                        len(dl_resp.content) // 1024,
                                    )
                                    downloaded += 1
                                    pdf_ok = True
                                    break
                    if not pdf_ok:
                        logger.warning("  Aucun flux PDF trouvé pour %s", entry.handle)

            except Exception as exc:
                logger.error("  Erreur lors du téléchargement de %s : %s", entry.filename, exc)

    logger.info("Fin du téléchargement PDF : %d/%d disponibles dans %s", downloaded, total, pdf_dir)
    return downloaded


def export_markdown(documents: list[ScrapedDocument], target_dir: Path | None = None) -> None:
    """Exporte les documents scrapés en fichiers Markdown individuels."""
    out_dir = target_dir or (PROJECT_ROOT / "data" / "sources_markdown")
    out_dir.mkdir(parents=True, exist_ok=True)

    for i, doc in enumerate(documents, 1):
        clean_title = re.sub(r"[^\w\-_\. ]", "_", doc.title).strip()[:40]
        filename = f"{i:02d}_{doc.source}_{clean_title}.md"
        filepath = out_dir / filename

        content = (
            f"# {doc.title}\n\n"
            f"- **Source :** {doc.source}\n"
            f"- **Thématique :** {doc.topic}\n"
            f"- **Langue :** {doc.language}\n"
            f"- **URL officielle :** {doc.url}\n"
            f"- **Date d'extraction :** {doc.scraped_at}\n\n"
            f"---\n\n"
            f"## Contenu\n\n"
            f"{doc.text}\n"
        )
        filepath.write_text(content, encoding="utf-8")

    logger.info("Export Markdown terminé : %d fichiers dans %s", len(documents), out_dir)


def main() -> None:
    """Point d'entrée exécutable autonome : scrape le Web et télécharge tous les PDF."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%H:%M:%S",
    )
    logger.info("=== Lancement de la collecte intégrale du corpus Lafiya ===")

    # 1. Scraping des pages Web
    logger.info("\n--- 1. Collecte des pages Web officielles ---")
    documents = scrape_sources(SOURCES)

    # Sauvegarde JSON et Markdown
    json_path = PROJECT_ROOT / "scripts" / "ingest" / "scraped_docs.json"
    json_path.write_text(
        json.dumps([asdict(d) for d in documents], indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    export_markdown(documents)

    # 2. Téléchargement des PDF officiels
    logger.info("\n--- 2. Téléchargement des guides officiels PDF ---")
    download_pdf_sources(PDF_SOURCES)

    logger.info("\n=== Collecte intégrale terminée avec succès ! ===")


if __name__ == "__main__":
    main()
