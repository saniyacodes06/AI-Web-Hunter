import unittest

from scraper.cleaner import (
    clean_html,
    content_hash,
    is_near_duplicate,
    jaccard_similarity,
    normalize_for_match,
    relevance_score,
)


SAMPLE_HTML = """
<html>
  <head>
    <title>Startup raises funding</title>
    <meta property="article:published_time" content="2026-11-10T10:00:00Z" />
  </head>
  <body>
    <nav>Home About Contact</nav>
    <article>
      <h1>Startup raises funding</h1>
      <p>Example AI Labs raised $20 million in a Series A funding round.</p>
      <p>The company will use the capital to hire engineers and launch a new product.</p>
      <script>window.secret = "do not keep";</script>
    </article>
    <footer>All rights reserved.</footer>
  </body>
</html>
"""


class CleanerTests(unittest.TestCase):
    def test_clean_html_extracts_article_and_removes_scripts(self):
        page = clean_html(SAMPLE_HTML, "https://example.com/a")
        self.assertEqual(page["title"], "Startup raises funding")
        self.assertIn("raised $20 million", page["content"])
        self.assertNotIn("window.secret", page["content"])
        self.assertEqual(page["published_at"], "2026-11-10T10:00:00Z")

    def test_hash_ignores_case_and_punctuation(self):
        self.assertEqual(
            content_hash("AI funding is growing!"),
            content_hash("ai funding is growing"),
        )

    def test_near_duplicate_detection(self):
        first = (
            "Example AI Labs raised twenty million dollars to build new tools "
            "for enterprise customers and hire more engineers."
        )
        second = (
            "Example AI Labs raised twenty million dollars to build new tools "
            "for enterprise customers and hire more engineers."
        )
        unrelated = "A completely different article about sports and weather."
        self.assertGreater(jaccard_similarity(first, second), 0.9)
        self.assertTrue(is_near_duplicate(first, [second]))
        self.assertFalse(is_near_duplicate(first, [unrelated]))

    def test_relevance_rewards_topic_words(self):
        topic = "AI funding"
        relevant = relevance_score(
            "The AI startup raised funding from investors.",
            "AI startup funding round",
            topic,
            [],
        )
        unrelated = relevance_score(
            "The local football team won a match on Saturday.",
            "Weekend sports results",
            topic,
            [],
        )
        self.assertGreater(relevant, unrelated)
        self.assertEqual(
            normalize_for_match("AI -- Funding!"), "ai funding"
        )


if __name__ == "__main__":
    unittest.main()
