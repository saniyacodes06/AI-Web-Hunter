import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from analyzer.pipeline import PipelineError, run_topic_scan
from utils.database import get_run_frames, get_runs, initialize_database


def fake_search(topic, keywords=None, permitted_domains=None, max_results=80, progress=None):
    return [
        {
            "url": f"https://techcrunch.com/2026/11/0{index}/article-{index}/",
            "title": f"AI funding article {index}",
            "domain": "techcrunch.com",
            "snippet": "AI funding news",
            "search_query": "test",
        }
        for index in (1, 2)
    ]


def fake_crawl(
    candidates,
    topic,
    keywords=None,
    max_pages=30,
    permitted_domains=None,
    progress=None,
):
    pages = []
    for index, candidate in enumerate(candidates[:max_pages], start=1):
        pages.append(
            {
                "url": candidate["url"],
                "domain": "techcrunch.com",
                "title": candidate["title"],
                "content": (
                    f"Company {index} raised $10 million in funding. "
                    "The company will hire engineers."
                ),
                "published_at": "2026-11-10T10:00:00Z",
                "word_count": 12,
                "content_hash": f"hash-{index}",
                "relevance_score": 0.8,
                "status": "success",
                "error": None,
            }
        )
    return {
        "pages": pages,
        "attempted": len(pages),
        "domains": ["techcrunch.com"],
        "errors": [],
        "skipped": [],
    }


def fake_extract(page, topic, keywords=None, provider=None, use_ai=True):
    return {
        "signals": [
            {
                "signal_type": "funding",
                "category": "Funding & investment",
                "entity": f"Company {page['url'][-2]}",
                "summary": "A company raised funding.",
                "evidence": page["content"].split(".")[0] + ".",
                "why_it_matters": "Shows investor demand.",
                "evidence_score": 8,
                "confidence": 90,
                "relevance": 9,
                "recency": 0.85,
                "evidence_verified": True,
                "extraction_method": "ai",
                "source_url": page["url"],
                "source_domain": page["domain"],
                "source_title": page["title"],
                "published_at": page["published_at"],
                "topic": topic,
                "keywords": keywords or [],
                "dedupe_key": f"key-{page['url']}",
            }
        ],
        "extraction_method": "ai",
        "error": None,
    }


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tempdir.name) / "test.db"
        self.patch_db = patch("utils.database.DB_PATH", self.db_path)
        self.patch_db.start()
        initialize_database()

    def tearDown(self):
        self.patch_db.stop()
        self.tempdir.cleanup()

    def test_complete_scan_persists_results(self):
        result = run_topic_scan(
            topic="AI funding",
            keywords="funding",
            page_limit=5,
            permitted_domains=["techcrunch.com"],
            provider="groq",
            search_fn=fake_search,
            crawl_fn=fake_crawl,
            extract_fn=fake_extract,
        )
        self.assertIsNotNone(result["run_id"])
        self.assertEqual(len(result["pages"]), 2)
        self.assertEqual(len(result["signals"]), 2)
        self.assertGreaterEqual(len(result["opportunities"]), 1)

        frames = get_run_frames(result["run_id"])
        self.assertEqual(len(frames["pages"]), 2)
        self.assertEqual(len(frames["signals"]), 2)
        self.assertGreaterEqual(len(frames["opportunities"]), 1)

    def test_no_candidates_marks_run_failed(self):
        with self.assertRaises(PipelineError):
            run_topic_scan(
                topic="AI funding",
                page_limit=5,
                permitted_domains=["techcrunch.com"],
                search_fn=lambda *args, **kwargs: [],
                crawl_fn=fake_crawl,
                extract_fn=fake_extract,
            )
        runs = get_runs(limit=1)
        self.assertEqual(runs[0]["status"], "failed")
        self.assertTrue(runs[0]["error"])


if __name__ == "__main__":
    unittest.main()
