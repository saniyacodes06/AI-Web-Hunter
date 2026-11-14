import unittest

from analyzer.opportunity_ranker import (
    build_opportunities,
    score_signal_group,
)
from config import OPPORTUNITY_WEIGHTS


def make_signal(
    index,
    signal_type="funding",
    domain="techcrunch.com",
    entity=None,
    published_at="2026-11-10T10:00:00Z",
):
    return {
        "id": index,
        "signal_type": signal_type,
        "category": signal_type,
        "entity": entity or f"Company {index}",
        "summary": f"Company {index} has a verified {signal_type} signal.",
        "evidence": f"Company {index} announced a {signal_type} update.",
        "why_it_matters": "It matters for the market.",
        "evidence_score": 8,
        "confidence": 85,
        "relevance": 9,
        "recency": 0.85,
        "source_domain": domain,
        "source_url": f"https://{domain}/article-{index}",
        "source_title": f"Source {index}",
        "published_at": published_at,
    }


class RankerTests(unittest.TestCase):
    def test_score_is_bounded_and_transparent(self):
        signals = [make_signal(index) for index in range(3)]
        scoring = score_signal_group(
            signals,
            permitted_domains=["techcrunch.com", "venturebeat.com", "theverge.com"],
        )
        self.assertGreaterEqual(scoring["score"], 0)
        self.assertLessEqual(scoring["score"], 100)
        self.assertAlmostEqual(sum(OPPORTUNITY_WEIGHTS.values()), 1.0)
        self.assertIn("formula", scoring["score_breakdown"])
        self.assertEqual(
            set(scoring["score_breakdown"]["components"]),
            set(OPPORTUNITY_WEIGHTS),
        )

    def test_top_five_limit_and_evidence_links(self):
        signals = []
        types = [
            "funding",
            "product_launch",
            "hiring",
            "partnership",
            "acquisition",
            "research",
        ]
        for index, signal_type in enumerate(types):
            signals.append(make_signal(index, signal_type=signal_type))
        opportunities = build_opportunities(
            signals,
            topic="AI",
            permitted_domains=["techcrunch.com"],
            limit=5,
        )
        self.assertEqual(len(opportunities), 5)
        scores = [item["score"] for item in opportunities]
        self.assertEqual(scores, sorted(scores, reverse=True))
        for opportunity in opportunities:
            self.assertGreaterEqual(opportunity["signal_count"], 1)
            self.assertTrue(opportunity["evidence"])
            self.assertTrue(opportunity["evidence"][0]["source_url"].startswith("https://"))

    def test_entity_split_when_few_types(self):
        signals = [
            make_signal(1, entity="Alpha"),
            make_signal(2, entity="Beta"),
            make_signal(3, entity="Gamma"),
        ]
        opportunities = build_opportunities(
            signals,
            topic="AI funding",
            permitted_domains=["techcrunch.com"],
            limit=5,
        )
        self.assertGreaterEqual(len(opportunities), 2)

    def test_empty_signals_return_no_opportunities(self):
        self.assertEqual(build_opportunities([], topic="AI"), [])


if __name__ == "__main__":
    unittest.main()
