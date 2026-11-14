"""CSV/JSON exports and a human-readable findings note."""

import json
from pathlib import Path

from config import EXPORTS_DIR
from utils.database import get_run, get_run_frames


def _frame_records(frame):
    if frame is None or frame.empty:
        return []
    return json.loads(
        frame.to_json(orient="records", date_format="iso", force_ascii=False)
    )


def export_run(run_id, exports_dir=None):
    """Write pages, signals, opportunities and a combined JSON export."""
    exports_dir = Path(exports_dir or EXPORTS_DIR)
    exports_dir.mkdir(parents=True, exist_ok=True)

    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run {run_id} does not exist.")

    frames = get_run_frames(run_id)
    pages = frames["pages"]
    signals = frames["signals"]
    opportunities = frames["opportunities"]

    paths = {
        "pages_csv": exports_dir / f"run_{run_id}_pages.csv",
        "signals_csv": exports_dir / f"run_{run_id}_signals.csv",
        "opportunities_csv": exports_dir / f"run_{run_id}_opportunities.csv",
        "opportunities_json": exports_dir / f"run_{run_id}_opportunities.json",
        "findings_json": exports_dir / f"run_{run_id}_findings.json",
        "findings_md": exports_dir / f"run_{run_id}_findings.md",
    }

    pages.to_csv(paths["pages_csv"], index=False)
    signals.to_csv(paths["signals_csv"], index=False)
    opportunities.to_csv(paths["opportunities_csv"], index=False)

    with paths["opportunities_json"].open("w", encoding="utf-8") as file:
        json.dump(
            _frame_records(opportunities),
            file,
            indent=2,
            ensure_ascii=False,
        )

    combined = {
        "run": run,
        "pages": _frame_records(pages),
        "signals": _frame_records(signals),
        "opportunities": _frame_records(opportunities),
    }
    with paths["findings_json"].open("w", encoding="utf-8") as file:
        json.dump(combined, file, indent=2, ensure_ascii=False)

    paths["findings_md"].write_text(build_findings_markdown(run_id), encoding="utf-8")
    return {key: str(value) for key, value in paths.items()}


def build_findings_markdown(run_id):
    run = get_run(run_id)
    if not run:
        raise ValueError(f"Run {run_id} does not exist.")

    frames = get_run_frames(run_id)
    pages = frames["pages"]
    signals = frames["signals"]
    opportunities = frames["opportunities"]

    lines = [
        f"# Findings: {run['topic']}",
        "",
        f"- Run ID: {run['id']}",
        f"- Started: {run.get('started_at')}",
        f"- Status: {run.get('status')}",
        f"- AI provider: {run.get('provider')}",
        f"- Permitted domains: {', '.join(run.get('permitted_domains') or [])}",
        f"- Pages kept: {len(pages)}",
        f"- Signals extracted: {len(signals)}",
        f"- Opportunities ranked: {len(opportunities)}",
        "",
        "## Top opportunities",
        "",
    ]

    if opportunities.empty:
        lines.append("No opportunities were produced by this run.")
    else:
        for _, opportunity in opportunities.head(5).iterrows():
            lines.extend(
                [
                    f"### {opportunity['rank_no']}. {opportunity['title']}",
                    "",
                    f"**Score:** {opportunity['score']:.2f}/100  ",
                    f"**Signals:** {opportunity['signal_count']}  ",
                    f"**Sources:** {opportunity['source_count']}  ",
                    "",
                    opportunity["summary"],
                    "",
                    f"**Why now:** {opportunity['why_now']}",
                    "",
                    f"**Recommended action:** {opportunity['recommended_action']}",
                    "",
                    "**Evidence:**",
                    "",
                ]
            )
            evidence = opportunity.get("evidence") or []
            for item in evidence[:5]:
                quote = str(item.get("quote", "")).replace("\n", " ")
                lines.append(
                    f"- \"{quote}\" - "
                    f"[{item.get('source_title') or item.get('source_domain')}]"
                    f"({item.get('source_url')})"
                )
            lines.append("")

    lines.extend(
        [
            "## Source coverage",
            "",
            "| Domain | Pages |",
            "|---|---:|",
        ]
    )
    if not pages.empty:
        for domain, count in pages["domain"].value_counts().items():
            lines.append(f"| {domain} | {count} |")
    else:
        lines.append("| _No pages_ | 0 |")

    lines.extend(
        [
            "",
            "> These findings are generated from live crawled pages. "
            "Quotes are verified against the stored page text. "
            "Always open the source links before acting.",
            "",
        ]
    )
    return "\n".join(lines)
