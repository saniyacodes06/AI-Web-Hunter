import unittest

from scraper.searcher import (
    _balanced_selection,
    _parse_feed,
    canonicalize_url,
    is_article_like,
)


RSS = b"""<?xml version="1.0"?>
<rss version="2.0"><channel>
<item>
  <title>AI startup raises funding</title>
  <link>https://techcrunch.com/2026/11/01/ai-startup/</link>
  <description><![CDATA[<p>A funding story.</p>]]></description>
  <pubDate>Mon, 02 Nov 2026 10:00:00 GMT</pubDate>
</item>
</channel></rss>
"""

ATOM = b"""<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom">
<entry>
  <title>New AI product</title>
  <link href="https://www.theverge.com/news/new-ai-product" />
  <summary>A product launch.</summary>
  <published>2026-11-03T10:00:00Z</published>
</entry>
</feed>
"""


class SearcherTests(unittest.TestCase):
    def test_canonicalize_url_removes_tracking_and_www(self):
        url = (
            "https://www.techcrunch.com/2026/11/01/ai-startup/"
            "?utm_source=test&utm_medium=social&id=7#comments"
        )
        self.assertEqual(
            canonicalize_url(url),
            "https://techcrunch.com/2026/11/01/ai-startup?id=7",
        )

    def test_article_like_filters_navigation(self):
        self.assertTrue(
            is_article_like("https://techcrunch.com/2026/11/01/ai-startup/")
        )
        self.assertFalse(is_article_like("https://techcrunch.com/category/ai/"))
        self.assertFalse(is_article_like("https://techcrunch.com/feed/"))
        self.assertFalse(
            is_article_like("https://techcrunch.com/2026/11/01/image.jpg")
        )

    def test_parse_rss_and_atom(self):
        rss_items = _parse_feed(RSS)
        self.assertEqual(len(rss_items), 1)
        self.assertEqual(rss_items[0]["title"], "AI startup raises funding")
        self.assertIn("funding story", rss_items[0]["snippet"])
        self.assertTrue(rss_items[0]["published_at"].startswith("2026-11-02"))

        atom_items = _parse_feed(ATOM)
        self.assertEqual(len(atom_items), 1)
        self.assertEqual(atom_items[0]["url"], "https://www.theverge.com/news/new-ai-product")

    def test_balanced_selection_uses_all_domains(self):
        results = []
        for index in range(10):
            results.append(
                {
                    "url": f"https://a.com/{index}",
                    "domain": "a.com",
                    "relevance_hint": 0.9,
                    "title": f"A {index}",
                }
            )
        results.append(
            {"url": "https://b.com/1", "domain": "b.com", "relevance_hint": 0.5, "title": "B"}
        )
        results.append(
            {"url": "https://c.com/1", "domain": "c.com", "relevance_hint": 0.4, "title": "C"}
        )
        selected = _balanced_selection(results, 6, ["a.com", "b.com", "c.com"])
        domains = [item["domain"] for item in selected]
        self.assertEqual(len(selected), 6)
        self.assertEqual(domains.count("a.com"), 4)
        self.assertEqual(domains.count("b.com"), 1)
        self.assertEqual(domains.count("c.com"), 1)
        self.assertEqual(set(domains), {"a.com", "b.com", "c.com"})


if __name__ == "__main__":
    unittest.main()
