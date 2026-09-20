"""
Article Extractor Service — fetches and extracts full text content from article URLs.

Uses trafilatura as the primary extraction engine (cleanly strips ads, navbars,
and boilerplate) with a BeautifulSoup fallback. Executes concurrently across
multiple URLs with strict timeouts to prevent ingestion pipeline bottlenecks.
"""

import logging
import re
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from app.config import settings

logger = logging.getLogger(__name__)

# Standard browser User-Agent to avoid immediate 403 Forbidden on news sites
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def _clean_extracted_text(text: str) -> str:
    """Normalize whitespace and remove redundant empty lines."""
    if not text:
        return ""
    # Replace multiple spaces or tabs
    text = re.sub(r"[ \t]+", " ", text)
    # Replace more than 2 consecutive newlines with 2 newlines
    text = re.sub(r"\n\s*\n+", "\n\n", text)
    return text.strip()


def extract_article_content(url: str, timeout: Optional[int] = None) -> Optional[str]:
    """
    Fetch a single URL and extract the main article body.
    Returns cleaned article text, or None if extraction fails or is blocked.
    """
    if not url or not settings.enable_article_extraction:
        return None

    fetch_timeout = timeout or settings.article_fetch_timeout_sec
    html_content = None

    # 1. Download webpage HTML using primp (bypasses Cloudflare/Akamai TLS checks) or urllib
    try:
        import primp
        client = primp.Client(impersonate="chrome_131")
        resp = client.get(url, timeout=fetch_timeout)
        if resp.status_code == 200:
            html_content = resp.text
    except Exception as primp_err:
        logger.debug(f"primp fetch failed for {url}: {primp_err}")

    # Fallback to urllib if primp failed or wasn't available
    if not html_content:
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": DEFAULT_USER_AGENT,
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            with urllib.request.urlopen(req, timeout=fetch_timeout) as response:
                content_type = response.headers.get("Content-Type", "")
                if "text/html" in content_type or "xhtml" in content_type:
                    raw_bytes = response.read(1_500_000)
                    try:
                        html_content = raw_bytes.decode("utf-8", errors="replace")
                    except Exception:
                        html_content = raw_bytes.decode("latin-1", errors="ignore")
        except Exception as fetch_err:
            logger.debug(f"urllib fetch failed for {url}: {fetch_err}")
            try:
                import trafilatura
                html_content = trafilatura.fetch_url(url)
            except Exception:
                pass

    if not html_content:
        return None

    # 2. Primary extraction: trafilatura (best-in-class news extraction)
    try:
        import trafilatura
        extracted = trafilatura.extract(
            html_content,
            url=url,
            include_comments=False,
            include_tables=False,
            no_fallback=False,
            favor_recall=True,
        )
        if extracted and len(extracted.strip()) > 100:
            cleaned = _clean_extracted_text(extracted)
            return cleaned
    except ImportError:
        logger.warning("trafilatura not installed; falling back to BeautifulSoup.")
    except Exception as traf_err:
        logger.debug(f"trafilatura extraction failed for {url}: {traf_err}")

    # 3. Fallback extraction: BeautifulSoup
    try:
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(html_content, "html.parser")

        # Strip scripts, styles, navigations, footers, headers
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form", "svg"]):
            tag.decompose()

        # Find main article container if present
        article_elem = soup.find("article") or soup.find("main") or soup.find(class_=re.compile(r"article|story|content|body", re.I))
        target = article_elem if article_elem else soup.body

        if target:
            paragraphs = [p.get_text(separator=" ", strip=True) for p in target.find_all("p")]
            # Filter out very short lines like "Share on Twitter", etc.
            valid_paragraphs = [p for p in paragraphs if len(p) > 35]
            if valid_paragraphs:
                text = "\n\n".join(valid_paragraphs)
                if len(text.strip()) > 100:
                    return _clean_extracted_text(text)
    except Exception as bs_err:
        logger.debug(f"BeautifulSoup fallback extraction failed for {url}: {bs_err}")

    return None


def extract_articles_batch(urls: List[str]) -> Dict[str, Optional[str]]:
    """
    Extract full text for a list of URLs concurrently.
    Returns a dict mapping url -> extracted_text (or None if failed).
    """
    if not urls or not settings.enable_article_extraction:
        return {url: None for url in urls}

    unique_urls = list(set(urls))
    results: Dict[str, Optional[str]] = {}
    max_workers = min(len(unique_urls), settings.article_max_workers)

    logger.info(f"Extracting full text for {len(unique_urls)} articles using {max_workers} workers...")

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_url = {
            executor.submit(extract_article_content, url): url
            for url in unique_urls
        }
        for future in as_completed(future_to_url):
            url = future_to_url[future]
            try:
                content = future.result()
                results[url] = content
                if content:
                    logger.debug(f"Extracted {len(content)} chars from {url}")
                else:
                    logger.debug(f"No body extracted from {url} (fallback to summary)")
            except Exception as e:
                logger.warning(f"Error during extraction for {url}: {e}")
                results[url] = None

    success_count = sum(1 for c in results.values() if c)
    logger.info(f"Full text extraction complete: {success_count}/{len(unique_urls)} articles extracted.")
    return results
