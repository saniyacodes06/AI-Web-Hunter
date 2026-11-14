import unittest
from unittest.mock import patch

from analyzer.signal_extractor import (
    _normalize_signal,
    extract_signals_for_page,
    fallback_extract,
)


PAGE = {
    "url": "https://techcrunch.com/2026/11/01/example/",
    "domain": "techcrunch.com",
    "title": "Example AI raises funding",
    "content": (
        "Example AI raised $20 million in a Series A funding round. "
        "The company will use the capital to hire engineers and launch a new product."
    ),
    "published_at": "2026-11-10T10:00:00Z",
    "relevance_score": 0.8,
}


class SignalExtractorTests(unittest.TestCase):
    def test_verified_ai_quote_is_kept(self):
        raw = {
            "signal_type": "funding",
            "entity": "Example AI",
            "summary": "Example AI raised a Series A round.",
            "evidence": "Example AI raised $20 million in a Series A funding round.",
            "why_it_matters": "Shows investor demand.",
            "evidence_score": 9,
            "confidence": 92,
            "relevance": 10,
        }
        signal = _normalize_signal(
            raw,
            PAGE,
            topic="AI funding",
            keywords=["funding"],
            method="ai",
            page_relevance=0.8,
        )
        self.assertIsNotNone(signal)
        self.assertTrue(signal["evidence_verified"])
        self.assertEqual(signal["signal_type"], "funding")
        self.assertEqual(signal["extraction_method"], "ai")

    def test_fabricated_ai_quote_is_rejected(self):
        raw = {
            "signal_type": "funding",
            "entity": "Example AI",
            "summary": "Invented fact.",
            "evidence": "Example AI raised $5 billion from the government.",
            "evidence_score": 10,
            "confidence": 99,
            "relevance": 10,
        }
        signal = _normalize_signal(
            raw,
            PAGE,
            topic="AI funding",
            keywords=["funding"],
            method="ai",
            page_relevance=0.8,
        )
        self.assertIsNone(signal)

    def test_keyword_fallback_uses_real_quotes(self):
        signals = fallback_extract(PAGE, "AI funding", keywords=["funding"])
        self.assertGreaterEqual(len(signals), 1)
        for signal in signals:
            self.assertEqual(signal["extraction_method"], "fallback_keyword")
            self.assertIn(signal["evidence"], PAGE["content"])

    @patch("analyzer.signal_extractor.provider_available", return_value=True)
    @patch("analyzer.signal_extractor.extract_page_signals")
    def test_fallback_when_ai_raises(self, mock_extract, mock_available):
        mock_extract.side_effect = RuntimeError("quota exceeded")
        result = extract_signals_for_page(
            PAGE,
            "AI funding",
            keywords=["funding"],
            provider="groq",
            use_ai=True,
        )
        self.assertEqual(result["extraction_method"], "fallback_keyword")
        self.assertIn("quota exceeded", result["error"])
        self.assertGreaterEqual(len(result["signals"]), 1)

    def test_ai_disabled_uses_fallback(self):
        result = extract_signals_for_page(
            PAGE,
            "AI funding",
            keywords=["funding"],
            provider="groq",
            use_ai=False,
        )
        self.assertEqual(result["extraction_method"], "fallback_keyword")


if __name__ == "__main__":
    unittest.main()
