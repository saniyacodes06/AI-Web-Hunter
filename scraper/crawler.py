
from concurrent.futures import ThreadPoolExecutor, as_completed
import re
import time
import hashlib
from datetime import datetime, timezone
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; SignalHunterResearchBot/1.0)"
}
TIMEOUT = 12
MIN_TEXT_CHARS = 350


def _robots_allowed(url, session):
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

    try:
        response = session.get(
            robots_url,
            timeout=5,
            headers=HEADERS
        )

        if response.status_code == 200:
            rp = RobotFileParser()
            rp.parse(response.text.splitlines())
            return rp.can_fetch(HEADERS["User-Agent"], url)

        if response.status_code in (401, 403):
            return False

        return True

    except requests.RequestException:
        return False


def _clean_page(html):
    soup = BeautifulSoup(html, "html.parser")

    title = (
        soup.title.get_text(" ", strip=True)
        if soup.title else "Untitled page"
    )

    for node in soup([
        "script", "style", "noscript", "svg",
        "header", "footer", "nav", "form", "aside"
    ]):
        node.decompose()

    for node in soup.select(
        "[class*='cookie'], [id*='cookie'], "
        "[class*='nav'], [class*='menu'], "
        "[class*='footer'], [class*='header'], "
        "[aria-hidden='true']"
    ):
        node.decompose()

    main = soup.find("main") or soup.find("article") or soup.body or soup

    text = re.sub(r"\s+", " ", main.get_text(" ", strip=True))
    text = re.sub(
        r"(accept all cookies|cookie settings|privacy policy|subscribe to our newsletter)",
        " ",
        text,
        flags=re.I
    )
    text = re.sub(r"\s+", " ", text).strip()

    return title[:250], text[:14000]


def _discover_ddg(query, limit):
    from ddgs import DDGS

    results = []
    seen = set()

    try:
        with DDGS() as ddgs:
            search_results = ddgs.text(
                query,
                max_results=limit
            )

            for item in search_results:
                title = item.get("title", "").strip()
                href = item.get("href", "").strip()

                if not title or not href:
                    continue

                parsed = urlparse(href)

                if parsed.scheme not in ("http", "https"):
                    continue

                if not parsed.netloc or href in seen:
                    continue

                seen.add(href)
                results.append((title, href))

    except Exception as error:
        print(f"SEARCH ERROR: {error}")

    print(f"Discovered {len(results)} URLs for: {query}")
    return results


def discover_and_crawl(
    topic,
    keywords="",
    page_limit=25,
    progress_callback=None
):
    session = requests.Session()

    # 1. Discover URLs using multiple search queries
    queries = [
        topic,
        f"{topic} problems and challenges",
        f"{topic} user reviews and complaints",
        f"{topic} business case studies",
        f"{topic} pricing and customer experience"
    ]

    if keywords.strip():
        queries.extend([
            f"{topic} {word.strip()}"
            for word in keywords.split(",")
            if word.strip()
        ])

    candidates = []
    seen_urls = set()

    # Search for more URLs because some pages may be inaccessible.
    per_query = min(max(page_limit * 3, 30), 100)

    try:
        for query in queries:
            results = _discover_ddg(query, per_query)

            for title, url in results:
                clean_url = url.split("#")[0].rstrip("/")
                parsed = urlparse(clean_url)

                if parsed.scheme not in ("http", "https"):
                    continue

                if not parsed.netloc:
                    continue

                if clean_url not in seen_urls:
                    seen_urls.add(clean_url)
                    candidates.append((title, clean_url))

            print("TOTAL CANDIDATES:", len(candidates))

            if len(candidates) >= page_limit * 8:
                break

            time.sleep(1)

    finally:
        session.close()

    print("TOTAL DISCOVERED URLS:", len(candidates))

    # 2. Fetch individual pages
    def fetch_page(search_title, url):
        parsed = urlparse(url)

        if re.search(
            r"\.(pdf|jpg|jpeg|png|gif|zip|mp4|mp3)(\?|$)",
            parsed.path,
            re.I
        ):
            return None

        worker_session = requests.Session()

        try:
            if not _robots_allowed(url, worker_session):
                return None

            response = worker_session.get(
                url,
                headers=HEADERS,
                timeout=TIMEOUT,
                allow_redirects=True
            )

            response.raise_for_status()

            content_type = response.headers.get(
                "Content-Type", ""
            ).lower()

            if "text/html" not in content_type:
                return None

            title, text = _clean_page(response.text)

            if len(text) < MIN_TEXT_CHARS:
                return None

            final_url = response.url
            final_domain = (
                urlparse(final_url)
                .netloc.lower()
                .removeprefix("www.")
            )

            return {
                "title": title or search_title,
                "url": final_url,
                "domain": final_domain,
                "crawl_date": datetime.now(
                    timezone.utc
                ).isoformat(),
                "text": text
            }

        except requests.RequestException as error:
            print(f"FETCH FAILED: {url} | {error}")
            return None

        finally:
            worker_session.close()

    # 3. Process candidates in small batches
    pages = []
    seen_content = set()
    seen_final_urls = set()

    batch_size = 15

    for start in range(0, len(candidates), batch_size):
        if len(pages) >= page_limit:
            break

        batch = candidates[start:start + batch_size]

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(fetch_page, title, url): url
                for title, url in batch
            }

            for future in as_completed(futures):
                try:
                    page = future.result()
                except Exception as error:
                    print("PAGE ERROR:", error)
                    continue

                if not page:
                    continue

                if page["url"] in seen_final_urls:
                    continue

                digest = hashlib.sha256(
                    re.sub(
                        r"\W+", "",
                        page["text"].lower()
                    ).encode()
                ).hexdigest()

                if digest in seen_content:
                    continue

                seen_content.add(digest)
                seen_final_urls.add(page["url"])
                pages.append(page)

                print(
                    f"SUCCESS: {len(pages)}/{page_limit} "
                    f"| {page['domain']}"
                )

                if progress_callback:
                    progress_callback(
                        min(len(pages), page_limit),
                        page_limit
                    )

                if len(pages) >= page_limit:
                    break

        if len(pages) < page_limit:
            time.sleep(1)

    print("FINAL CRAWLED PAGES:", len(pages))
    print(
        "SUCCESSFUL DOMAINS:",
        sorted({page["domain"] for page in pages})
    )

    return pages
