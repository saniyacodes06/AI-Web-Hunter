"""Command-line runner for a complete topic scan.

Example:
    python run_pipeline.py --topic "AI funding and product launches" \
        --keywords "funding, launch, hiring" --limit 30
"""

import argparse
import sys
from pathlib import Path

from analyzer.pipeline import PipelineError, run_topic_scan
from config import AI_PROVIDER, DEFAULT_PAGE_LIMIT, PERMITTED_DOMAINS
from utils.exporter import build_findings_markdown, export_run


def parse_args():
    parser = argparse.ArgumentParser(description="Run an AI Web Signal Hunter scan.")
    parser.add_argument("--topic", required=True, help="Topic to investigate")
    parser.add_argument(
        "--keywords",
        default="",
        help="Optional comma-separated keywords",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=DEFAULT_PAGE_LIMIT,
        help="Maximum number of pages to keep",
    )
    parser.add_argument(
        "--domains",
        default=",".join(PERMITTED_DOMAINS),
        help="Comma-separated permitted domains",
    )
    parser.add_argument(
        "--provider",
        default=AI_PROVIDER,
        choices=["groq", "gemini"],
        help="AI provider",
    )
    parser.add_argument(
        "--no-ai",
        action="store_true",
        help="Use the deterministic keyword fallback (for testing only)",
    )
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="Do not write CSV/JSON exports",
    )
    parser.add_argument(
        "--findings-out",
        default=None,
        help="Optional path for a Markdown findings note",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    domains = [part.strip() for part in args.domains.split(",") if part.strip()]

    try:
        result = run_topic_scan(
            topic=args.topic,
            keywords=args.keywords,
            page_limit=args.limit,
            permitted_domains=domains,
            provider=args.provider,
            use_ai=not args.no_ai,
            progress=lambda message: print(f"- {message}"),
        )
    except PipelineError as exc:
        print(f"\nScan failed: {exc}", file=sys.stderr)
        return 1

    run = result["run"]
    print("\nScan complete")
    print(f"Run ID: {run['id']}")
    print(f"Status: {run['status']}")
    print(f"Candidates found: {result['candidates_found']}")
    print(f"Pages kept: {len(result['pages'])}")
    print(f"Domains covered: {', '.join(result['domains'])}")
    print(f"Signals: {len(result['signals'])}")
    print(f"Opportunities: {len(result['opportunities'])}")

    if result["warnings"]:
        print("\nWarnings:")
        for warning in result["warnings"]:
            print(f"- {warning}")

    print("\nTop opportunities:")
    for index, opportunity in enumerate(result["opportunities"], start=1):
        print(
            f"{index}. {opportunity['title']} "
            f"(score {opportunity['score']:.2f}, "
            f"{opportunity['signal_count']} signals, "
            f"{opportunity['source_count']} sources)"
        )
        print(f"   {opportunity['summary'][:300]}")
        for item in opportunity["evidence"][:2]:
            print(f"   Evidence: {item['source_url']}")

    if not args.no_export:
        paths = export_run(result["run_id"])
        print("\nExports:")
        for label, path in paths.items():
            print(f"- {label}: {path}")

        if args.findings_out:
            output = Path(args.findings_out)
            output.write_text(build_findings_markdown(result["run_id"]), encoding="utf-8")
            print(f"- findings note: {output}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
