from __future__ import annotations

import json
import unittest

from bs4 import BeautifulSoup

from crossfit_wods.parse import extract_wod_block, parse_one
from crossfit_wods.scraper import classify_page


class ConservativeIngestionTests(unittest.TestCase):
    def test_classify_page_requires_structure_for_wod(self) -> None:
        html = """
        <html><body><article>
        <h2>Workout of the Day</h2>
        <ul><li>For Time</li><li>21-15-9 Thruster 95 lb</li><li>Run 400 m</li></ul>
        </article></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "wod")

    def test_classify_page_unknown_when_only_weak_markers(self) -> None:
        html = "<html><body><p>For time discussion and AMRAP theory article.</p></body></html>"
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "unknown")

    def test_classify_page_detects_wod_in_main_layout(self) -> None:
        html = """
        <html><body><main>
        <h2>Workout of the Day</h2>
        <p>For Time</p>
        <ul><li>21-15-9 reps of thruster (95 lb) and pull-up</li></ul>
        </main></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "wod")

    def test_extract_wod_block_ambiguous_without_measure_or_movement(self) -> None:
        block, ambiguous = extract_wod_block("Warm-up\nFor Time\nGo hard")
        self.assertIsNotNone(block)
        self.assertTrue(ambiguous)

    def test_extract_wod_block_can_start_on_reps_line(self) -> None:
        raw_text = "Header\nGeneral info\n21-15-9 reps of thruster (95 lb) and pull-up\nShare"
        block, ambiguous = extract_wod_block(raw_text)
        self.assertIn("21-15-9", block or "")
        self.assertFalse(ambiguous)

    def test_parse_one_sets_needs_review_on_ambiguous_wod(self) -> None:
        row = {
            "wod_date": "2024-01-01",
            "resolved_url": "https://example.com",
            "page_type": "wod",
            "raw_text": "Header\nFor Time\nPush it",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "needs_review")
        tags = json.loads(payload["tags_json"])
        self.assertIn("needs_review", tags)


if __name__ == "__main__":
    unittest.main()
