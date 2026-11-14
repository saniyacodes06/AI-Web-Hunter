import unittest

from analyzer.ai_analyzer import AIError, parse_json_response


class JSONParsingTests(unittest.TestCase):
    def test_plain_json(self):
        self.assertEqual(parse_json_response('{"signals": []}'), {"signals": []})

    def test_markdown_fenced_json(self):
        text = 'Here you go:\n```json\n{"page_summary": "x", "signals": []}\n```'
        self.assertEqual(
            parse_json_response(text),
            {"page_summary": "x", "signals": []},
        )

    def test_json_embedded_in_prose(self):
        text = 'The result is {"signals": [{"signal_type": "funding"}]} as requested.'
        parsed = parse_json_response(text)
        self.assertEqual(parsed["signals"][0]["signal_type"], "funding")

    def test_invalid_json_raises(self):
        with self.assertRaises(AIError):
            parse_json_response("not json at all")


if __name__ == "__main__":
    unittest.main()
