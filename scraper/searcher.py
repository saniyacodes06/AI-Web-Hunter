"""Find relevant pages on the permitted domains.

The searcher tries public web search first, then uses domain search APIs, RSS
feeds and article links from homepages. Every result is real and every URL is
checked against the permitted-domain allowlist.
"""

import base64
import re
import time
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import parse_qs, urlencode, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from config import (
    CRAWL_DELAY_SECONDS,
    DOMAIN_FEEDS,
    PERMITTED_DOMAINS,
    REQUEST_TIMEOUT_SECONDS,
    USER_AGENT,
)
from scraper.cleaner import (
    is_allowed_url,
    normalize_domain,
    normalize_text,
    relevance_score,
)

TRACKING_PARAMS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_term",
    "utm_content",
    "fbclid",
    "gclid",
    "oc",
    "ref",
    "source",
    "mc_cid",
    "mc_eid",
}

BLOCKED_PATH_PARTS = {
    "about",
    "author",
    "authors",
    "category",
    "categories",
    "contact",
    "feed",
    "feeds",
    "login",
    "newsletter",
    "page",
    "privacy",
    "rss",
    "search",
    "signup",
    "subscribe",
    "tag",
    "tags",
    "terms",
    "video",
    "videos",
    "wp-json",
    "wp-admin",
}

BLOCKED_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".svg",
    ".css",
    ".js",
    ".json",
    ".xml",
    ".pdf",
    ".zip",
)


def _headers():
    return {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }


def canonicalize_url(url):
    """Remove tracking parameters and standardise a URL for deduplication."""
    if not url:
        return ""
    url = url.strip()
    if url.startswith("//"):
        url = "https:" + url

    parsed = urlparse(url)
    if not parsed.scheme:
        return url

    host = parsed.netloc.lower()
    if host.startswith("www."):
        host = host[4:]

    path = re.sub(r"/amp/?$", "/", parsed.path)
    path = re.sub(r"/{2,}", "/", path)
    if path != "/":
        path = path.rstrip("/")

    query_pairs = []
    for key, value in parse_qs(parsed.query, keep_blank_values=False).items():
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith("utm_"):
            query_pairs.append((key, value[0]))

    return urlunparse(
        (
            parsed.scheme.lower() or "https",
            host,
            path,
            "",
            urlencode(sorted(query_pairs)),
            "",
        )
    )


def is_article_like(url):
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return False
    path = parsed.path.lower()
    if path in ("", "/"):
        return False
    if path.endswith(BLOCKED_EXTENSIONS):
        return False
    parts = [part for part in path.split("/") if part]
    if any(part in BLOCKED_PATH_PARTS for part in parts):
        return False
    return len(parts) >= 1


def _add_result(results, seen, item, topic, keywords, allowed_domains):
    url = canonicalize_url(item.get("url", ""))
    if not url or url in seen or not is_article_like(url):
        return
    if not is_allowed_url(url, allowed_domains):
        return

    title = normalize_text(item.get("title", ""))
    snippet = normalize_text(item.get("snippet", ""))
    if len(title) < 5:
        return

    seen.add(url)
    results.append(
        {
            "url": url,
            "title": title,
            "snippet": snippet,
            "domain": normalize_domain(url),
            "published_at": item.get("published_at"),
            "search_query": item.get("search_query", ""),
            "source_kind": item.get("source_kind", "web_search"),
            "relevance_hint": relevance_score(
                snippet, title, topic, keywords
            ),
        }
    )


def _decode_duckduckgo_url(href):
    if not href:
        return ""
    if href.startswith("//"):
        href = "https:" + href
    if "duckduckgo.com/l/" in href:
        query = parse_qs(urlparse(href).query)
        return query.get("uddg", [""])[0]
    return href


def _duckduckgo_search(query, max_results=15):
    response = requests.get(
        "https://html.duckduckgo.com/html/",
        params={"q": query},
        headers=_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    for result in soup.select(".result")[:max_results]:
        anchor = result.select_one("a.result__a")
        if not anchor:
            continue
        snippet_tag = result.select_one(".result__snippet")
        items.append(
            {
                "url": _decode_duckduckgo_url(anchor.get("href")),
                "title": anchor.get_text(" ", strip=True),
                "snippet": snippet_tag.get_text(" ", strip=True) if snippet_tag else "",
                "search_query": query,
                "source_kind": "duckduckgo",
            }
        )
    return items


def _decode_bing_url(href):
    if not href:
        return ""
    if "bing.com/ck/a" in href:
        value = parse_qs(urlparse(href).query).get("u", [""])[0]
        if value.startswith("a1"):
            value = value[2:]
            padding = "=" * (-len(value) % 4)
            try:
                return base64.urlsafe_b64decode(value + padding).decode(
                    "utf-8", errors="ignore"
                )
            except (ValueError, TypeError):
                return ""
    return href


def _bing_search(query, max_results=15):
    response = requests.get(
        "https://www.bing.com/search",
        params={"q": query, "setlang": "en-US", "cc": "US"},
        headers=_headers(),
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    for result in soup.select("li.b_algo")[:max_results]:
        anchor = result.select_one("h2 a")
        if not anchor:
            continue
        caption = result.select_one(".b_caption p")
        items.append(
            {
                "url": _decode_bing_url(anchor.get("href")),
                "title": anchor.get_text(" ", strip=True),
                "snippet": caption.get_text(" ", strip=True) if caption else "",
                "search_query": query,
                "source_kind": "bing",
            }
        )
    return items


def _parse_rss_date(value):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError):
        return normalize_text(value)


def _parse_feed(xml_bytes):
    """Parse both RSS 2.0 and Atom feeds into simple dictionaries."""
    try:
        root = ET.fromstring(xml_bytes)
    except ET.ParseError:
        return []

    atom_ns = "{http://www.w3.org/2005/Atom}"
    items = root.findall(".//item")
    atom_entries = root.findall(f".//{atom_ns}entry")

    parsed = []
    for item in items:
        parsed.append(
            {
                "title": item.findtext("title", default=""),
                "url": item.findtext("link", default=""),
                "snippet": BeautifulSoup(
                    item.findtext("description", default=""), "html.parser"
                ).get_text(" ", strip=True),
                "published_at": _parse_rss_date(item.findtext("pubDate")),
            }
        )

    for entry in atom_entries:
        link_tag = entry.find(f"{atom_ns}link")
        url = ""
        if link_tag is not None:
            url = link_tag.get("href", "")
        summary = entry.findtext(f"{atom_ns}summary", default="")
        if not summary:
            summary = entry.findtext(f"{atom_ns}content", default="")
        parsed.append(
            {
                "title": entry.findtext(f"{atom_ns}title", default=""),
                "url": url,
                "snippet": BeautifulSoup(summary, "html.parser").get_text(
                    " ", strip=True
                ),
                "published_at": _parse_rss_date(
                    entry.findtext(f"{atom_ns}published")
                    or entry.findtext(f"{atom_ns}updated")
                ),
            }
        )
    return parsed


def _discover_feed_urls(domain):
    feed_urls = list(DOMAIN_FEEDS.get(domain, []))
    try:
        response = requests.get(
            f"https://{domain}/", headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS
        )
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")
            for link in soup.find_all("link", rel="alternate"):
                link_type = (link.get("type") or "").lower()
                href = link.get("href") or ""
                if ("rss" in link_type or "atom" in link_type) and href:
                    feed_urls.append(urljoin(f"https://{domain}/", href))
    except requests.RequestException:
        pass

    for candidate in (f"https://{domain}/feed/", f"https://{domain}/rss"):
        if candidate not in feed_urls:
            feed_urls.append(candidate)

    seen = set()
    unique = []
    for url in feed_urls:
        canonical = canonicalize_url(url)
        if canonical and canonical not in seen:
            seen.add(canonical)
            unique.append(url)
    return unique[:6]


def _rss_results(domain, topic, keywords, max_items=60):
    items = []
    for feed_url in _discover_feed_urls(domain):
        try:
            response = requests.get(
                feed_url,
                headers=_headers(),
                timeout=REQUEST_TIMEOUT_SECONDS,
            )
            if response.status_code != 200:
                continue
            for entry in _parse_feed(response.content)[:max_items]:
                entry["search_query"] = f"feed:{feed_url}"
                entry["source_kind"] = "rss_feed"
                items.append(entry)
        except requests.RequestException:
            continue
        time.sleep(min(CRAWL_DELAY_SECONDS, 0.2))
    return items


def _homepage_links(domain, topic, keywords, max_items=30):
    try:
        response = requests.get(
            f"https://{domain}/", headers=_headers(), timeout=REQUEST_TIMEOUT_SECONDS
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    items = []
    seen = set()
    for anchor in soup.find_all("a", href=True):
        url = canonicalize_url(urljoin(f"https://{domain}/", anchor["href"]))
        title = normalize_text(anchor.get_text(" ", strip=True))
        if (
            not url
            or url in seen
            or len(title) < 20
            or not is_article_like(url)
            or normalize_domain(url) != domain
        ):
            continue
        seen.add(url)
        items.append(
            {
                "url": url,
                "title": title,
                "snippet": "",
                "search_query": "homepage_links",
                "source_kind": "homepage",
            }
        )
        if len(items) >= max_items:
            break
    return items


def _wordpress_search(domain, query, per_page=30):
    endpoint = f"https://{domain}/wp-json/wp/v2/posts"
    try:
        response = requests.get(
            endpoint,
            params={
                "search": query,
                "per_page": per_page,
                "_fields": "link,title,date,excerpt",
            },
            headers=_headers(),
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return []
    if response.status_code != 200:
        return []

    try:
        posts = response.json()
    except ValueError:
        return []
    if not isinstance(posts, list):
        return []

    items = []
    for post in posts:
        title = post.get("title", {})
        excerpt = post.get("excerpt", {})
        items.append(
            {
                "url": post.get("link", ""),
                "title": title.get("rendered", "") if isinstance(title, dict) else title,
                "snippet": BeautifulSoup(
                    excerpt.get("rendered", "")
                    if isinstance(excerpt, dict)
                    else str(excerpt),
                    "html.parser",
                ).get_text(" ", strip=True),
                "published_at": post.get("date"),
                "search_query": query,
                "source_kind": "wordpress_search",
            }
        )
    return items


def _balanced_selection(results, max_results, domains):
    """Round-robin by domain so one large source cannot crowd out the others."""
    by_domain = {domain: [] for domain in domains}
    for result in results:
        by_domain.setdefault(result["domain"], []).append(result)

    for domain in by_domain:
        by_domain[domain].sort(
            key=lambda item: (item["relevance_hint"], item["title"]), reverse=True
        )

    selected = []
    while len(selected) < max_results and any(by_domain.values()):
        for domain in domains:
            bucket = by_domain.get(domain, [])
            if bucket:
                selected.append(bucket.pop(0))
                if len(selected) >= max_results:
                    break
    return selected


def search_topic(
    topic,
    keywords=None,
    permitted_domains=None,
    max_results=80,
    progress=None,
):
    """Search for topic-relevant article candidates.

    Returns a list of dictionaries. No page is fabricated: every item comes from
    a live search result, feed entry, WordPress API response or homepage link.
    """
    allowed_domains = tuple(
        normalize_domain(domain)
        for domain in (permitted_domains or PERMITTED_DOMAINS)
    )

    keywords = keywords or []
    if isinstance(keywords, str):
        keywords = [part.strip() for part in keywords.split(",") if part.strip()]

    queries = [topic]
    if keywords:
        queries.append(f"{topic} {' '.join(keywords)}")
        queries.append(" ".join(keywords))

    results = []
    seen = set()

    def report(message):
        if progress:
            progress(message)

    for query in queries[:3]:
        for engine_name, engine in (
            ("DuckDuckGo", _duckduckgo_search),
            ("Bing", _bing_search),
        ):
            try:
                found = engine(query)
            except requests.RequestException:
                found = []
            for item in found:
                _add_result(results, seen, item, topic, keywords, allowed_domains)
            if found:
                report(f"{engine_name}: {len(found)} raw results for '{query}'")
        time.sleep(min(CRAWL_DELAY_SECONDS, 0.3))

    for domain in allowed_domains:
        try:
            wp_items = _wordpress_search(domain, topic)
        except requests.RequestException:
            wp_items = []
        for item in wp_items:
            _add_result(results, seen, item, topic, keywords, allowed_domains)
        if wp_items:
            report(f"WordPress search: {len(wp_items)} results from {domain}")

        feed_items = _rss_results(domain, topic, keywords)
        for item in feed_items:
            _add_result(results, seen, item, topic, keywords, allowed_domains)
        if feed_items:
            report(f"RSS: {len(feed_items)} feed entries from {domain}")

        home_items = _homepage_links(domain, topic, keywords)
        for item in home_items:
            _add_result(results, seen, item, topic, keywords, allowed_domains)
        if home_items:
            report(f"Homepage: {len(home_items)} links from {domain}")

        time.sleep(min(CRAWL_DELAY_SECONDS, 0.3))

    selected = _balanced_selection(results, max_results, list(allowed_domains))
    report(
        "Candidate pool: "
        f"{len(selected)} pages across "
        f"{len({item['domain'] for item in selected})} domains"
    )
    return selected
