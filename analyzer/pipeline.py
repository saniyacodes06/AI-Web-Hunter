"""End-to-end topic scan: search -> crawl -> AI extraction -> rank -> store."""

from config import (
    AI_PROVIDER,
    DEFAULT_PAGE_LIMIT,
    MAX_PAGE_LIMIT,
    MIN_REQUIRED_PAGES,
    PERMITTED_DOMAINS,
)
from analyzer.opportunity_ranker import build_opportunities
from analyzer.signal_extractor import (
    extract_signals_for_page,
    extract_signals_for_pages,
)
from scraper.cleaner import normalize_domain
from scraper.crawler import crawl_candidates
from scraper.searcher import canonicalize_url, search_topic
from utils.database import (
    create_run,
    finish_run,
    get_run,
    initialize_database,
    save_opportunities,
    save_page,
    save_signal,
)


class PipelineError(RuntimeError):
    """Raised when a scan cannot produce a usable result."""


def _parse_keywords(keywords):
    if not keywords:
        return []
    if isinstance(keywords, str):
        return [part.strip() for part in keywords.split(",") if part.strip()]
    return [str(part).strip() for part in keywords if str(part).strip()]


def run_topic_scan(
    topic,
    keywords=None,
    page_limit=DEFAULT_PAGE_LIMIT,
    permitted_domains=None,
    provider=None,
    use_ai=True,
    progress=None,
    search_fn=None,
    crawl_fn=None,
    extract_fn=None,
    batch_extract_fn=None,
):
    """Run a complete scan and return in-memory results plus the run ID."""
    topic = (topic or "").strip()
    if not topic:
        raise PipelineError("Topic is required.")

    keywords = _parse_keywords(keywords)
    page_limit = max(5, min(int(page_limit or DEFAULT_PAGE_LIMIT), MAX_PAGE_LIMIT))
    provider = (provider or AI_PROVIDER).lower()
    permitted_domains = [
        normalize_domain(domain)
        for domain in (permitted_domains or PERMITTED_DOMAINS)
        if normalize_domain(domain)
    ]
    if not permitted_domains:
        raise PipelineError("At least one permitted domain is required.")

    search_fn = search_fn or search_topic
    crawl_fn = crawl_fn or crawl_candidates
    batch_mode = extract_fn is None
    extract_fn = extract_fn or extract_signals_for_page
    batch_extract_fn = batch_extract_fn or extract_signals_for_pages

    def report(message):
        if progress:
            progress(message)

    initialize_database()
    run_id = create_run(
        topic=topic,
        keywords=keywords,
        page_limit=page_limit,
        permitted_domains=permitted_domains,
        provider=provider,
    )

    warnings = []
    crawl_report = {}
    candidates = []
    pages = []
    signals = []
    opportunities = []

    try:
        report(f"Searching for: {topic}")
        candidates = search_fn(
            topic,
            keywords=keywords,
            permitted_domains=permitted_domains,
            max_results=max(page_limit * 3, 60),
            progress=progress,
        )
        if not candidates:
            raise PipelineError(
                "No candidate pages were found. Check your network connection, "
                "the permitted domains, or try a broader topic."
            )

        report(f"Found {len(candidates)} candidate pages. Crawling...")
        crawl_report = crawl_fn(
            candidates,
            topic,
            keywords=keywords,
            max_pages=page_limit,
            permitted_domains=permitted_domains,
            progress=progress,
        )
        pages = crawl_report.get("pages", [])
        if not pages:
            raise PipelineError(
                "Candidate pages were found but none could be crawled and kept. "
                "The sources may be blocking requests or the pages may be duplicates."
            )

        candidate_by_url = {
            canonicalize_url(item.get("url", "")): item for item in candidates
        }

        report(f"Extracting signals from {len(pages)} pages...")
        page_records = []
        for page in pages:
            search_query = candidate_by_url.get(
                canonicalize_url(page.get("url", "")), {}
            ).get("search_query")
            page_id = save_page(run_id, page, search_query=search_query)
            page_records.append((page, page_id))

        if batch_mode:
            report(
                f"Using batched AI extraction for {len(page_records)} pages..."
            )
            try:
                extractions = batch_extract_fn(
                    pages,
                    topic,
                    keywords=keywords,
                    provider=provider,
                    use_ai=use_ai,
                    progress=report,
                )
                if len(extractions) != len(page_records):
                    raise ValueError(
                        "Batch extractor returned a different number of results."
                    )
            except Exception as exc:
                warnings.append(
                    f"Batch extraction failed: {str(exc)[:250]}. "
                    "Keyword fallback was used for all pages."
                )
                extractions = [
                    extract_signals_for_page(
                        page,
                        topic,
                        keywords=keywords,
                        provider=provider,
                        use_ai=False,
                    )
                    for page, _ in page_records
                ]
        else:
            extractions = []
            for page, _ in page_records:
                try:
                    extractions.append(
                        extract_fn(
                            page,
                            topic,
                            keywords=keywords,
                            provider=provider,
                            use_ai=use_ai,
                        )
                    )
                except Exception as exc:
                    warnings.append(
                        f"Extraction failed for {page.get('url')}: "
                        f"{str(exc)[:200]}"
                    )
                    extractions.append(
                        {"signals": [], "extraction_method": "failed"}
                    )

        fallback_pages = 0
        extraction_error_count = 0
        extraction_error_examples = []
        for index, ((page, page_id), extraction) in enumerate(
            zip(page_records, extractions), start=1
        ):
            if extraction.get("extraction_method") == "fallback_keyword":
                fallback_pages += 1
            if extraction.get("error"):
                error_text = str(extraction["error"])
                if not (not use_ai and "AI disabled" in error_text):
                    extraction_error_count += 1
                    if len(extraction_error_examples) < 3:
                        extraction_error_examples.append(
                            f"{page.get('domain')}: {error_text[:180]}"
                        )

            for signal in extraction.get("signals", []):
                signal_id = save_signal(run_id, page_id, signal)
                signal["id"] = signal_id
                signal["page_id"] = page_id
                signals.append(signal)

            if index == len(page_records) or index % 5 == 0:
                report(
                    f"Stored signals for {index}/{len(page_records)} pages "
                    f"({len(signals)} signals so far)."
                )

        report("Grouping and ranking opportunities...")
        opportunities = build_opportunities(
            signals,
            topic=topic,
            keywords=keywords,
            permitted_domains=permitted_domains,
            limit=5,
        )
        save_opportunities(run_id, opportunities)

        covered_domains = sorted({page["domain"] for page in pages})
        if len(pages) < MIN_REQUIRED_PAGES:
            warnings.append(
                f"Only {len(pages)} pages were kept; the assignment target is "
                f"{MIN_REQUIRED_PAGES} when enough relevant pages are available."
            )
        if len(covered_domains) < len(permitted_domains):
            warnings.append(
                "Coverage was uneven: "
                f"{len(covered_domains)} of {len(permitted_domains)} permitted "
                "domains produced at least one kept page."
            )
        if crawl_report.get("errors"):
            warnings.append(
                f"{len(crawl_report['errors'])} pages could not be fetched."
            )
        if fallback_pages:
            warnings.append(
                f"{fallback_pages} pages used the keyword fallback instead of AI. "
                "Check the API key, quota or provider logs."
            )
        if extraction_error_count:
            warnings.append(
                f"{extraction_error_count} pages had extraction errors. "
                "Examples: " + " | ".join(extraction_error_examples)
            )

        status = "completed_with_warnings" if warnings else "completed"
        finish_run(
            run_id,
            status=status,
            pages_found=len(candidates),
            pages_crawled=crawl_report.get("attempted", 0),
            pages_kept=len(pages),
            signals_count=len(signals),
            opportunities_count=len(opportunities),
            warnings=warnings,
        )
        report("Scan complete.")
        return {
            "run_id": run_id,
            "run": get_run(run_id),
            "candidates_found": len(candidates),
            "pages": pages,
            "signals": signals,
            "opportunities": opportunities,
            "warnings": warnings,
            "crawl_report": crawl_report,
            "domains": covered_domains,
        }

    except Exception as exc:
        finish_run(
            run_id,
            status="failed",
            pages_found=len(candidates),
            pages_crawled=crawl_report.get("attempted", 0),
            pages_kept=len(pages),
            signals_count=len(signals),
            opportunities_count=len(opportunities),
            warnings=warnings,
            error=str(exc)[:1000],
        )
        if isinstance(exc, PipelineError):
            raise
        raise PipelineError(str(exc)) from exc
