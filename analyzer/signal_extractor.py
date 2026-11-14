"""Validate AI output, verify evidence and provide a keyword fallback."""

import re

from analyzer.ai_analyzer import (
    extract_batch_signals,
    extract_page_signals,
    provider_available,
)
from config import AI_BATCH_SIZE
from scraper.cleaner import (
    content_hash,
    normalize_for_match,
    normalize_text,
    recency_score,
)

SIGNAL_TYPES = {
    "funding": {
        "label": "Funding & investment",
        "action": "Track the investors, round size and stated use of funds.",
    },
    "product_launch": {
        "label": "Product launches",
        "action": "Check whether the launch creates a competitive or integration opportunity.",
    },
    "hiring": {
        "label": "Hiring & talent",
        "action": "Look for teams or skills that signal a new strategic priority.",
    },
    "partnership": {
        "label": "Partnerships & alliances",
        "action": "Map the partners and assess whether the alliance changes market access.",
    },
    "acquisition": {
        "label": "M&A and acquisitions",
        "action": "Review the acquired capability and possible market consolidation.",
    },
    "expansion": {
        "label": "Market expansion",
        "action": "Check which geography or customer segment is being prioritised.",
    },
    "research": {
        "label": "Research & technology",
        "action": "Assess whether the technical claim is independently reproducible.",
    },
    "regulation": {
        "label": "Policy & regulation",
        "action": "Track compliance deadlines and which products are affected.",
    },
    "customer_win": {
        "label": "Customer wins",
        "action": "Check contract details and whether the customer reference is verifiable.",
    },
    "other": {
        "label": "Other signals",
        "action": "Read the original source and validate the business relevance.",
    },
}

TYPE_ALIASES = {
    "funding": "funding",
    "investment": "funding",
    "investor": "funding",
    "product launch": "product_launch",
    "launch": "product_launch",
    "hiring": "hiring",
    "jobs": "hiring",
    "partnership": "partnership",
    "partnerships": "partnership",
    "acquisition": "acquisition",
    "merger": "acquisition",
    "expansion": "expansion",
    "research": "research",
    "technology": "research",
    "regulation": "regulation",
    "policy": "regulation",
    "customer win": "customer_win",
    "customer": "customer_win",
    "other": "other",
}

FALLBACK_PATTERNS = {
    "funding": re.compile(
        r"\b(raised|raising|funding|series [a-e]|investment|invested|valuation|"
        r"backed|capital|financing)\b",
        re.IGNORECASE,
    ),
    "product_launch": re.compile(
        r"\b(launch(ed|ing|es)?|unveil(ed|ing|s)?|release(d|s)?|introduc(ed|ing|es)?|"
        r"new (product|model|feature|tool|platform|service))\b",
        re.IGNORECASE,
    ),
    "hiring": re.compile(
        r"\b(hir(e|ing|es)|jobs?|careers?|recruit(ing|ment)?|talent|"
        r"employees?|headcount|workforce)\b",
        re.IGNORECASE,
    ),
    "partnership": re.compile(
        r"\b(partnership|partnered|partnering|collaborat(e|ed|ion)|"
        r"joint venture|alliance|teamed up)\b",
        re.IGNORECASE,
    ),
    "acquisition": re.compile(
        r"\b(acquir(e|ed|ing|sition)|merg(e|ed|er)|takeover|bought)\b",
        re.IGNORECASE,
    ),
    "expansion": re.compile(
        r"\b(expand(ed|ing|s)?|opened? (a )?(new )?(office|location|market)|"
        r"enters? .{0,30} market|new market)\b",
        re.IGNORECASE,
    ),
    "research": re.compile(
        r"\b(research|study|paper|benchmark|breakthrough|scientists?|"
        r"developed a|new model)\b",
        re.IGNORECASE,
    ),
    "regulation": re.compile(
        r"\b(regulat(e|ion|ors?)|law|policy|government|compliance|"
        r"antitrust|banned?)\b",
        re.IGNORECASE,
    ),
    "customer_win": re.compile(
        r"\b(customer|client|contract|selected|adopt(ed|s)?|deployment)\b",
        re.IGNORECASE,
    ),
}


def _clamp(value, minimum, maximum, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = default
    return round(max(minimum, min(maximum, number)), 2)


def _normalize_type(value):
    text = normalize_text(value).lower().replace("-", " ").replace("_", " ")
    text = re.sub(r"\s+", " ", text)
    if text in TYPE_ALIASES:
        return TYPE_ALIASES[text]
    if text.replace(" ", "_") in SIGNAL_TYPES:
        return text.replace(" ", "_")
    return "other"


def _quote_is_verified(evidence, content):
    quote = normalize_for_match(evidence)
    source = normalize_for_match(content)
    if len(quote) < 15:
        return False
    return quote in source


def _normalize_signal(raw, page, topic, keywords, method, page_relevance):
    signal_type = _normalize_type(raw.get("signal_type") or raw.get("category"))
    evidence = normalize_text(raw.get("evidence", ""))
    if not _quote_is_verified(evidence, page.get("content", "")):
        return None

    entity = normalize_text(raw.get("entity", ""))
    summary = normalize_text(raw.get("summary", ""))
    why = normalize_text(raw.get("why_it_matters", ""))

    if not summary:
        summary = evidence[:400]
    if not entity:
        entity = "Unspecified entity"

    evidence_score = _clamp(
        raw.get("evidence_score"), 0, 10, default=5
    )
    confidence = _clamp(raw.get("confidence"), 0, 100, default=60)
    relevance = _clamp(
        raw.get("relevance"),
        0,
        10,
        default=round((page_relevance or 0) * 10, 2),
    )

    return {
        "signal_type": signal_type,
        "category": SIGNAL_TYPES[signal_type]["label"],
        "entity": entity[:200],
        "summary": summary[:600],
        "evidence": evidence[:900],
        "why_it_matters": why[:600],
        "evidence_score": evidence_score,
        "confidence": confidence,
        "relevance": relevance,
        "recency": recency_score(page.get("published_at")),
        "evidence_verified": True,
        "extraction_method": method,
        "source_url": page.get("url"),
        "source_domain": page.get("domain"),
        "source_title": page.get("title"),
        "published_at": page.get("published_at"),
        "topic": topic,
        "keywords": keywords or [],
        "dedupe_key": content_hash(
            f"{page.get('url', '')}|{signal_type}|{evidence}"
        ),
    }


def _dedupe_signals(signals):
    seen = set()
    unique = []
    for signal in signals:
        key = signal.get("dedupe_key")
        if key and key not in seen:
            seen.add(key)
            unique.append(signal)
    return unique


def _split_sentences(content):
    candidates = re.split(r"(?<=[.!?])\s+|\n+", content)
    sentences = []
    for sentence in candidates:
        sentence = normalize_text(sentence)
        if 35 <= len(sentence) <= 700:
            sentences.append(sentence)
    return sentences


def _guess_entity(sentence, page_title):
    matches = re.findall(
        r"\b([A-Z][A-Za-z0-9&.-]*(?:\s+[A-Z][A-Za-z0-9&.-]*){0,2})\b",
        sentence,
    )
    stop_starts = {"The", "This", "A", "An", "It", "We", "They", "In", "On"}
    for match in sorted(matches, key=len, reverse=True):
        if match.split()[0] not in stop_starts and len(match) > 2:
            return match
    title = normalize_text(page_title)
    return title[:120] if title else "Unspecified entity"


def fallback_extract(page, topic, keywords=None):
    """Deterministic keyword extraction used only when AI is unavailable.

    It preserves real quotes from the page and marks each signal with
    extraction_method="fallback_keyword".
    """
    keywords = keywords or []
    content = page.get("content", "")
    page_relevance = page.get("relevance_score", 0)
    signals = []

    for sentence in _split_sentences(content):
        best_type = None
        best_hits = 0
        for signal_type, pattern in FALLBACK_PATTERNS.items():
            hits = len(pattern.findall(sentence))
            if hits > best_hits:
                best_type = signal_type
                best_hits = hits

        if not best_type:
            continue

        signals.append(
            {
                "signal_type": best_type,
                "entity": _guess_entity(sentence, page.get("title", "")),
                "summary": sentence[:400],
                "evidence": sentence,
                "why_it_matters": (
                    "Keyword-based extraction. Read the quote and source before acting."
                ),
                "evidence_score": min(4 + best_hits, 7),
                "confidence": 55,
                "relevance": round(max(page_relevance, 0.1) * 10, 2),
                "extraction_method": "fallback_keyword",
            }
        )

    normalized = []
    for raw in signals:
        signal = _normalize_signal(
            raw,
            page,
            topic,
            keywords,
            method="fallback_keyword",
            page_relevance=page_relevance,
        )
        if signal:
            normalized.append(signal)
    normalized.sort(
        key=lambda signal: (
            signal.get("evidence_score", 0),
            signal.get("confidence", 0),
            len(signal.get("evidence", "")),
        ),
        reverse=True,
    )
    return _dedupe_signals(normalized)[:6]


def extract_signals_for_page(
    page,
    topic,
    keywords=None,
    provider=None,
    use_ai=True,
):
    """Return validated signals plus extraction metadata for one page."""
    keywords = keywords or []
    raw_signals = []
    method = "ai"
    error = None
    page_summary = ""
    primary_theme = ""

    if use_ai and provider_available(provider):
        try:
            data = extract_page_signals(
                page, topic, keywords=keywords, provider=provider
            )
            raw_signals = data.get("signals", []) or []
            page_summary = normalize_text(data.get("page_summary", ""))
            primary_theme = normalize_text(data.get("primary_theme", ""))
        except Exception as exc:
            error = str(exc)[:500]
            method = "fallback_keyword"
            raw_signals = []
    elif use_ai:
        error = f"No API key configured for provider: {provider}"
        method = "fallback_keyword"
    else:
        method = "fallback_keyword"
        error = "AI disabled by user."

    validated = []
    dropped = 0
    for raw in raw_signals:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        signal = _normalize_signal(
            raw,
            page,
            topic,
            keywords,
            method=method,
            page_relevance=page.get("relevance_score", 0),
        )
        if signal:
            validated.append(signal)
        else:
            dropped += 1

    if raw_signals and not validated:
        error = (
            error
            or "AI quotes failed verification; keyword fallback was used instead."
        )
        method = "fallback_keyword"
        validated = fallback_extract(page, topic, keywords=keywords)

    if method == "fallback_keyword" and not validated:
        validated = fallback_extract(page, topic, keywords=keywords)

    return {
        "signals": _dedupe_signals(validated),
        "extraction_method": method,
        "error": error,
        "page_summary": page_summary,
        "primary_theme": primary_theme,
        "dropped_unverified": dropped,
    }


def _fallback_result(page, topic, keywords, error):
    return {
        "signals": fallback_extract(page, topic, keywords=keywords),
        "extraction_method": "fallback_keyword",
        "error": error,
        "page_summary": "",
        "primary_theme": "",
        "dropped_unverified": 0,
    }


def _validate_ai_page_entry(entry, page, topic, keywords):
    raw_signals = entry.get("signals", []) if isinstance(entry, dict) else []
    if not isinstance(raw_signals, list):
        raw_signals = []

    validated = []
    dropped = 0
    for raw in raw_signals:
        if not isinstance(raw, dict):
            dropped += 1
            continue
        signal = _normalize_signal(
            raw,
            page,
            topic,
            keywords,
            method="ai",
            page_relevance=page.get("relevance_score", 0),
        )
        if signal:
            validated.append(signal)
        else:
            dropped += 1

    error = None
    method = "ai"
    if raw_signals and not validated:
        method = "fallback_keyword"
        error = (
            "AI quotes failed verification for this page; keyword fallback "
            "was used instead."
        )
        validated = fallback_extract(page, topic, keywords=keywords)

    return {
        "signals": _dedupe_signals(validated),
        "extraction_method": method,
        "error": error,
        "page_summary": normalize_text(
            entry.get("page_summary", "") if isinstance(entry, dict) else ""
        ),
        "primary_theme": normalize_text(
            entry.get("primary_theme", "") if isinstance(entry, dict) else ""
        ),
        "dropped_unverified": dropped,
    }


def extract_signals_for_pages(
    pages,
    topic,
    keywords=None,
    provider=None,
    use_ai=True,
    progress=None,
):
    """Extract signals for many pages using batched AI calls.

    A batch of three pages normally finishes in one API round trip. If a batch
    fails, only that batch falls back to the verified keyword extractor.
    """
    keywords = keywords or []
    if not pages:
        return []

    def report(message):
        if progress:
            progress(message)

    if not use_ai:
        error = "AI disabled by user."
        return [
            _fallback_result(page, topic, keywords, error) for page in pages
        ]

    if not provider_available(provider):
        error = f"No API key configured for provider: {provider}"
        return [
            _fallback_result(page, topic, keywords, error) for page in pages
        ]

    batch_size = max(1, int(AI_BATCH_SIZE))
    results = []
    total_batches = (len(pages) + batch_size - 1) // batch_size

    for batch_number, start in enumerate(range(0, len(pages), batch_size), start=1):
        batch = pages[start : start + batch_size]
        try:
            data = extract_batch_signals(
                batch,
                topic,
                keywords=keywords,
                provider=provider,
            )
        except Exception as exc:
            error = f"AI batch failed: {str(exc)[:300]}"
            results.extend(
                _fallback_result(page, topic, keywords, error) for page in batch
            )
            report(
                f"AI batch {batch_number}/{total_batches} failed; "
                f"keyword fallback used for {len(batch)} pages."
            )
            continue

        entries = {}
        for entry in data.get("pages", []):
            if not isinstance(entry, dict):
                continue
            try:
                page_id = int(entry.get("page_id"))
            except (TypeError, ValueError):
                continue
            entries[page_id] = entry

        ai_signal_count = 0
        fallback_count = 0
        for offset, page in enumerate(batch, start=1):
            entry = entries.get(offset)
            if entry is None:
                results.append(
                    {
                        "signals": [],
                        "extraction_method": "ai",
                        "error": "The AI omitted this page from the batch response.",
                        "page_summary": "",
                        "primary_theme": "",
                        "dropped_unverified": 0,
                    }
                )
                continue
            result = _validate_ai_page_entry(entry, page, topic, keywords)
            if result["extraction_method"] == "fallback_keyword":
                fallback_count += 1
            else:
                ai_signal_count += len(result["signals"])
            results.append(result)

        report(
            f"AI batch {batch_number}/{total_batches}: "
            f"{ai_signal_count} verified signals, {fallback_count} fallback pages."
        )

    return results
