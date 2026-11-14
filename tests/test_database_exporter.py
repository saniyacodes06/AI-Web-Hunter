import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzer.opportunity_ranker import build_opportunities
from utils.database import (
    create_run,
    finish_run,
    get_pages_dataframe,
    get_run,
    get_run_frames,
    initialize_database,
    save_opportunities,
    save_page,
    save_signal,
)
from utils.exporter import export_run


PAGE = {
    "url": "https://techcrunch.com/2026/11/01/example/",
    "domain": "techcrunch.com",
    "title": "Example AI raises funding",
    "content": "Example AI raised $20 million in a Series A funding round.",
    "published_at": "2026-11-10T10:00:00Z",
    "word_count": 10,
    "content_hash": "abc123",
    "relevance_score": 0.9,
}

SIGNAL = {
    "signal_type": "funding",
    "category": "Funding & investment",
    "entity": "Example AI",
    "summary": "Example AI raised a Series A round.",
    "evidence": "Example AI raised $20 million in a Series A funding round.",
    "why_it_matters": "Shows investor demand.",
    "evidence_score": 9,
    "confidence": 92,
    "relevance": 10,
    "recency": 0.85,
    "evidence_verified": True,
    "extraction_method": "ai",
    "source_url": PAGE["url"],
    "source_domain": PAGE["domain"],
    "source_title": PAGE["title"],
    "published_at": PAGE["published_at"],
    "topic": "AI funding",
    "keywords": ["funding"],
    "dedupe_key": "signal-abc",
}


class DatabaseExporterTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "test.db"
        self.exports_dir = Path(self.tempdir.name) / "exports"
        self.patch_db = patch("utils.database.DB_PATH", self.db_path)
        self.patch_db.start()
        initialize_database()

    def tearDown(self):
        self.patch_db.stop()
        self.tempdir.cleanup()

    def test_round_trip_run_and_export(self):
        run_id = create_run(
            topic="AI funding",
            keywords=["funding"],
            page_limit=5,
            permitted_domains=["techcrunch.com"],
            provider="groq",
        )
        page_id = save_page(run_id, PAGE, search_query="test query")
        signal_id = save_signal(run_id, page_id, SIGNAL)
        signal = dict(SIGNAL)
        signal["id"] = signal_id
        opportunities = build_opportunities(
            [signal],
            topic="AI funding",
            permitted_domains=["techcrunch.com"],
        )
        save_opportunities(run_id, opportunities)
        finish_run(
            run_id,
            status="completed",
            pages_found=1,
            pages_crawled=1,
            pages_kept=1,
            signals_count=1,
            opportunities_count=len(opportunities),
        )

        run = get_run(run_id)
        self.assertEqual(run["status"], "completed")
        self.assertEqual(run["keywords"], ["funding"])

        pages = get_pages_dataframe(run_id)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages.iloc[0]["domain"], "techcrunch.com")

        frames = get_run_frames(run_id)
        self.assertEqual(len(frames["signals"]), 1)
        self.assertEqual(len(frames["opportunities"]), 1)
        self.assertIsInstance(frames["opportunities"].iloc[0]["evidence"], list)

        paths = export_run(run_id, exports_dir=self.exports_dir)
        for key, path in paths.items():
            self.assertTrue(Path(path).exists(), key)
        with open(paths["findings_json"], encoding="utf-8") as file:
            data = json.load(file)
        self.assertEqual(data["run"]["id"], run_id)
        self.assertEqual(len(data["signals"]), 1)
        self.assertIn("Evidence", Path(paths["findings_md"]).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
