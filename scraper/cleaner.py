"""HTML cleaning, text normalisation, deduplication and relevance helpers."""

import hashlib
import json
import re
from datetime import datetime, timezone
from urllib.parse import urlparse

from bs4 import BeautifulSoup

REMOVE_TAGS = [
    "script",
    "style",
    "noscript",
    "nav",
    "footer",
    "header",
    "aside",
    "form",
    "iframe",
    "svg",
    "button",
]

BOILERPLATE_PATTERNS = [
    r"accept all cookies",
    r"manage (your )?cookie",
    r"subscribe to (our )?newsletter",
    r"sign up for (our )?newsletter",
    r"advertisement",
    r"all rights reserved",
    r"follow us on",
    r"share this article",
    r"read more:?$",
]

STOPWORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "in",
    "is",
    "it",
    "its",
    "of",
    "on",
    "or",
    "that",
    "the",
    "this",
    "to",
    "was",
    "were",
    "will",
    "with",
    "about",
    "after",
    "before",
    "into",
    "over",
    "under",
    "their",
    "they",
    "you",
    "your",
}


def normalize_text(text):
    """Collapse whitespace so comparisons and AI evidence checks are stable."""
    if not text:
        return ""
    text = str(text).replace("\xa0", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{2,}", "\n", text)
    return text.strip()


def normalize_for_match(text):
    """Lowercase and remove punctuation for quote verification."""
    text = normalize_text(text).lower()
    return re.sub(r"[^a-z0-9]+", " ", text).strip()


def _is_boilerplate(line):
    lower = line.lower().strip()
    if not lower:
        return True
    if len(lower) < 25:
        return True
    return any(re.search(pattern, lower) for pattern in BOILERPLATE_PATTERNS)


def _clean_lines(lines):
    cleaned = []
    seen = set()
    for line in lines:
        line = normalize_text(line)
        if _is_boilerplate(line):
            continue
        key = normalize_for_match(line)
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(line)
    return cleaned


def _extract_json_ld_date(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(script.string or "")
        except (TypeError, ValueError):
            continue

        candidates = data if isinstance(data, list) else [data]
        for item in candidates:
            if not isinstance(item, dict):
                continue
            for key in ("datePublished", "dateCreated", "dateModified"):
                value = item.get(key)
                if value:
                    return str(value)
    return None


def extract_published_at(soup):
    """Read the most common publication-date hints from a page."""
    selectors = [
        ('meta[property="article:published_time"]', "content"),
        ('meta[name="article:published_time"]', "content"),
        ('meta[name="date"]', "content"),
        ('meta[itemprop="datePublished"]', "content"),
        ('time[datetime]', "datetime"),
    ]
    for selector, attribute in selectors:
        tag = soup.select_one(selector)
        if tag and tag.get(attribute):
            return normalize_text(tag.get(attribute))

    json_ld_date = _extract_json_ld_date(soup)
    if json_ld_date:
        return normalize_text(json_ld_date)
    return None


def clean_html(html, url=""):
    """Turn raw HTML into the title, readable article text and a date hint."""
    soup = BeautifulSoup(html or "", "html.parser")

    title = ""
    og_title = soup.select_one('meta[property="og:title"]')
    if og_title and og_title.get("content"):
        title = normalize_text(og_title["content"])
    elif soup.title and soup.title.get_text(strip=True):
        title = normalize_text(soup.title.get_text(" ", strip=True))

    published_at = extract_published_at(soup)

    for tag in soup.find_all(REMOVE_TAGS):
        tag.decompose()

    content_root = soup.find("article") or soup.find("main") or soup.body or soup
    lines = []
    for tag in content_root.find_all(["h1", "h2", "h3", "p", "li"]):
        text = tag.get_text(" ", strip=True)
        if text:
            lines.append(text)

    cleaned = _clean_lines(lines)

    if len(" ".join(cleaned)) < 200:
        fallback_lines = content_root.get_text("\n", strip=True).splitlines()
        cleaned = _clean_lines(fallback_lines)

    content = normalize_text("\n".join(cleaned))
    return {
        "title": title or "Untitled page",
        "content": content,
        "published_at": published_at,
    }


def content_hash(text):
    """Fast exact-duplicate fingerprint."""
    normalized = normalize_for_match(text)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def word_shingles(text, size=5):
    words = normalize_for_match(text).split()
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def jaccard_similarity(text_a, text_b, size=5):
    """Near-duplicate similarity based on overlapping word shingles."""
    a = word_shingles(text_a, size)
    b = word_shingles(text_b, size)
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def is_near_duplicate(text, other_texts, threshold=0.92):
    for other in other_texts:
        if jaccard_similarity(text, other) >= threshold:
            return True
    return False


def tokenize_topic(text):
    tokens = re.findall(r"[a-z0-9]+", (text or "").lower())
    return [token for token in tokens if token not in STOPWORDS and len(token) > 1]


def relevance_score(text, title, topic, keywords=None):
    """A transparent 0-1 relevance score based only on topic words."""
    keywords = keywords or []
    topic_text = " ".join([topic or ""] + list(keywords))
    tokens = tokenize_topic(topic_text)
    if not tokens:
        return 0.0

    title_lower = (title or "").lower()
    text_lower = (text or "").lower()
    title_tokens = set(tokenize_topic(title))
    body_tokens = set(tokenize_topic(text))
    wanted = set(tokens)

    title_hits = len(wanted & title_tokens)
    body_hits = len(wanted & body_tokens)

    token_score = (title_hits * 2 + body_hits) / (len(set(tokens)) * 3)
    phrase_hits = sum(
        1
        for phrase in [topic] + list(keywords)
        if phrase and str(phrase).lower() in (title_lower + " " + text_lower)
    )
    phrase_score = min(phrase_hits / max(1, len([topic] + list(keywords))), 1.0)

    return round(min(1.0, token_score * 0.7 + phrase_score * 0.3), 4)


def recency_score(published_at, now=None):
    """Convert a publication date into a 0-1 freshness score."""
    if not published_at:
        return 0.3

    now = now or datetime.now(timezone.utc)
    text = str(published_at).strip()
    try:
        if text.endswith("Z"):
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        else:
            parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return 0.3

    age_days = max((now - parsed).total_seconds() / 86400, 0)
    if age_days <= 7:
        return 1.0
    if age_days <= 14:
        return 0.85
    if age_days <= 30:
        return 0.65
    if age_days <= 90:
        return 0.4
    return 0.2


def normalize_domain(url_or_domain):
    value = (url_or_domain or "").strip().lower()
    if "://" in value:
        value = urlparse(value).netloc
    if value.startswith("www."):
        value = value[4:]
    return value.split(":")[0]


def is_allowed_url(url, permitted_domains):
    domain = normalize_domain(url)
    return any(
        domain == allowed or domain.endswith("." + allowed)
        for allowed in permitted_domains
    )
