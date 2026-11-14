import os
import re
import urllib.parse
from typing import List, Optional
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()


def scrape_website(
    url: str,
    api_key: Optional[str] = None,
    render_js: bool = False,
    timeout: int = 30,
) -> str:
    """
    Scrapes the target URL using Scrape.do API, or falls back to direct requests
    if no Scrape.do token is provided.

    Args:
        url: The website URL to scrape.
        api_key: Scrape.do API token (defaults to SCRAPE_DO_API_KEY from environment).
        render_js: Whether to execute JavaScript on the page via Scrape.do headless browser.
        timeout: Request timeout in seconds.

    Returns:
        The raw HTML string of the scraped webpage.
    """
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    token = api_key or os.getenv("SCRAPE_DO_API_KEY", "").strip()

    # Use Scrape.do if token is provided
    if token and token != "your_scrape_do_token_here":
        endpoint = "https://api.scrape.do"
        params = {
            "token": token,
            "url": url,
        }
        if render_js:
            params["render"] = "true"

        response = requests.get(endpoint, params=params, timeout=timeout)
        if response.status_code == 200:
            return response.text
        else:
            raise RuntimeError(
                f"Scrape.do request failed with status code {response.status_code}: {response.text}"
            )

    # Fallback to direct HTTP request with standard browser headers
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    html_text = response.text

    # Basic bot/protection check
    lower_html = html_text.lower()
    if "just a moment..." in lower_html or "cf-browser-verification" in lower_html:
        raise RuntimeError(
            "Target site is protected by Cloudflare bot management. "
            "Direct scraping was blocked. Please provide a Scrape.do API token with JS rendering enabled."
        )

    return html_text


def extract_body_content(html_content: str) -> str:
    """
    Extracts the <body> content from raw HTML.

    Args:
        html_content: Raw HTML content.

    Returns:
        HTML string of the <body> tag or full HTML if <body> is missing.
    """
    soup = BeautifulSoup(html_content, "html.parser")
    body = soup.body
    return str(body) if body else html_content


def clean_body_content(body_content: str, preserve_links: bool = True) -> str:
    """
    Cleans the HTML body content:
    - Removes non-content tags (scripts, styles, svg, iframe).
    - Preserves hyperlinks and image sources in readable text format if requested.
    - Strips redundant whitespaces and formatting noise.

    Args:
        body_content: HTML content of the body.
        preserve_links: When True, retains anchor hrefs and image sources inline.

    Returns:
        Cleaned plain text representation.
    """
    soup = BeautifulSoup(body_content, "html.parser")

    # Decompose script, style, and metadata tags
    for tag in soup(["script", "style", "noscript", "svg", "iframe"]):
        tag.decompose()

    # Convert hyperlinks to readable format: "Anchor Text (URL)"
    if preserve_links:
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()
            text = a_tag.get_text(strip=True)
            if href and text and not href.startswith(("javascript:", "#")):
                a_tag.replace_with(f" {text} ({href}) ")

        for img_tag in soup.find_all("img", src=True):
            src = img_tag["src"].strip()
            alt = img_tag.get("alt", "").strip() or "Image"
            if src and not src.startswith("data:"):
                img_tag.replace_with(f" [{alt}: {src}] ")

    # Extract clean text with newline separation
    raw_text = soup.get_text(separator="\n")

    # Clean up empty lines and trailing whitespaces
    cleaned_lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    cleaned_content = "\n".join(cleaned_lines)

    # Collapse excessive newlines
    cleaned_content = re.sub(r"\n{3,}", "\n\n", cleaned_content)
    return cleaned_content


def split_dom_content(
    dom_content: str, max_length: int = 6000, overlap: int = 300
) -> List[str]:
    """
    Splits cleaned DOM text into chunks of at most `max_length` characters,
    with an `overlap` margin to avoid cutting contextual information across chunks.

    Args:
        dom_content: Cleaned DOM text.
        max_length: Maximum character length per chunk.
        overlap: Character overlap between consecutive chunks.

    Returns:
        List of text chunks.
    """
    if not dom_content:
        return []

    if len(dom_content) <= max_length:
        return [dom_content]

    chunks = []
    start = 0
    content_len = len(dom_content)

    while start < content_len:
        end = min(start + max_length, content_len)

        # Try to break at a newline if we're not at the very end
        if end < content_len:
            last_newline = dom_content.rfind("\n", start, end)
            if last_newline != -1 and last_newline > start + (max_length // 2):
                end = last_newline

        chunk = dom_content[start:end].strip()
        if chunk:
            chunks.append(chunk)

        if end >= content_len:
            break

        # Move forward, maintaining overlap
        start = max(start + 1, end - overlap)

    return chunks
