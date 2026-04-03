from __future__ import annotations

import json
import unittest

from bs4 import BeautifulSoup

from crossfit_wods.parse import extract_wod_block, parse_one
from crossfit_wods.scraper import (
    classify_page,
    extract_main_text_from_html,
    explain_main_text_choice,
    is_comment_like_text,
)


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

    def test_classify_page_detects_old_school_strength_wod(self) -> None:
        html = """
        <html><body><article>
        <p>Find your best back squat at 5,3, and 1 reps</p>
        <p>Find your best deadlift at 5,3, and 1 reps</p>
        <p>Find your best bench-press at 5,3, and 1 reps</p>
        <p>Read the article for historical context and links.</p>
        </article></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "wod")

    def test_classify_page_keeps_editorial_article_conservative(self) -> None:
        html = """
        <html><body><article>
        <p>This article discusses how to find your best habits as a coach.</p>
        <p>It includes a 5,3,1 writing framework and opinion on nutrition.</p>
        <p>Podcast and article links are provided for additional reading.</p>
        </article></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "editorial_only")

    def test_classify_page_detects_monostructural_rounds_for_time_wod(self) -> None:
        html = """
        <html><body><article>
        <p>4 rounds, each for time of:</p>
        <p>800-meter run</p>
        </article></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertEqual(classify_page(soup, text), "wod")

    def test_classify_page_run_without_structure_is_not_wod(self) -> None:
        html = "<html><body><article><p>Today we talk about run technique and pacing.</p></article></body></html>"
        soup = BeautifulSoup(html, "lxml")
        text = soup.get_text("\n", strip=True)
        self.assertNotEqual(classify_page(soup, text), "wod")

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

    def test_parse_one_strength_block_stops_before_editorial_resource(self) -> None:
        row = {
            "wod_date": "2001-02-16",
            "resolved_url": "https://www.crossfit.com/workout/2001/02/16",
            "page_type": "wod",
            "raw_text": (
                "Find your best back squat at 5,3, and 1 reps\n"
                "Find your best deadlift at 5,3, and 1 reps\n"
                "Find your best bench-press at 5,3, and 1 reps\n"
                "Read this article for context\n"
                "https://example.com/resource"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "strength")
        self.assertIn("bench-press", payload["wod_text"] or "")
        self.assertNotIn("https://", payload["wod_text"] or "")

    def test_parse_one_monostructural_rounds_for_time_is_valid_wod(self) -> None:
        row = {
            "wod_date": "2002-01-01",
            "resolved_url": "https://www.crossfit.com/workout/2002/01/01",
            "page_type": "wod",
            "raw_text": "4 rounds, each for time of:\n800-meter run",
        }
        payload = parse_one(row)
        entities = json.loads(payload["movement_list_json"])
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "for_time")
        self.assertTrue(any(entity.get("movement_norm") == "run" for entity in entities))
        self.assertTrue(any(entity.get("kind") == "distance" and entity.get("value_source") == 800.0 for entity in entities))

    def test_parse_one_run_without_structure_is_needs_review(self) -> None:
        row = {
            "wod_date": "2002-01-02",
            "resolved_url": "https://www.crossfit.com/workout/2002/01/02",
            "page_type": "wod",
            "raw_text": "Run with good posture and breathing.",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "needs_review")

    def test_extract_main_text_ignores_comment_reply_and_footer_blocks(self) -> None:
        html = """
        <html><body>
          <main>
            <article id="post-1" class="entry-content">
              <h2>Workout of the Day</h2>
              <p>For Time</p>
              <p>4 rounds, each for time of:</p>
              <p>800-meter run</p>
            </article>
          </main>
          <section id="comments">
            <p>Yesterday I did this with a vest.</p>
            <a>Reply</a>
          </section>
          <footer>
            <p>Next Post</p>
          </footer>
        </body></html>
        """
        text = extract_main_text_from_html(html)
        self.assertIn("4 rounds, each for time of:", text)
        self.assertNotIn("Yesterday I did", text)
        self.assertNotIn("Reply", text)
        self.assertNotIn("Next Post", text)

    def test_explain_main_text_choice_returns_candidate_debug_info(self) -> None:
        html = """
        <html><body>
          <article class="entry-content">
            <h2>Workout of the Day</h2>
            <p>AMRAP 10</p>
            <p>Run 400 m</p>
          </article>
        </body></html>
        """
        info = explain_main_text_choice(html)
        self.assertIn("selector", info)
        self.assertIn("rationale", info)
        self.assertIsNotNone(info["container"])

    def test_extract_main_text_prefers_structured_json_article_body(self) -> None:
        html = """
        <html><body>
          <script type="application/ld+json">
            {
              "@type": "Article",
              "articleBody": "Workout of the Day\\n5 rounds for time of:\\nRun 400 m"
            }
          </script>
          <main><p>Reply</p><p>Modified tabata from 2026/03/30</p></main>
        </body></html>
        """
        text = extract_main_text_from_html(html)
        self.assertIn("5 rounds for time", text)
        self.assertNotIn("Modified tabata", text)

    def test_extract_main_text_supports_next_data_payload(self) -> None:
        html = """
        <html><body>
          <script id="__NEXT_DATA__" type="application/json">
            {"props": {"pageProps": {"post": {"content": "Workout of the Day\\n8' AMRAP\\n8 burpees"}}}}
          </script>
          <section id="comments"><p>Reply</p></section>
        </body></html>
        """
        info = explain_main_text_choice(html)
        self.assertEqual(info["source_type"], "structured_json")
        self.assertIn("AMRAP", info["preview"])

    def test_comment_like_text_detection(self) -> None:
        self.assertTrue(is_comment_like_text("Didn't have a rope climb, so I modified the program. Reply"))
        self.assertFalse(is_comment_like_text("Workout of the Day\n8 rounds for time of:\n5 pull-ups\n10 push-ups"))


if __name__ == "__main__":
    unittest.main()
