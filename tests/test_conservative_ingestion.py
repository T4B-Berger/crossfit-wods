from __future__ import annotations

import json
import unittest

from bs4 import BeautifulSoup

from crossfit_wods.parse import (
    detect_movements,
    detect_workout_format,
    extract_measurements,
    extract_ordered_movements,
    extract_wod_block,
    parse_one,
    score_wod_block,
    select_main_wod_block,
)
from crossfit_wods.scraper import (
    classify_page,
    extract_main_text_from_html,
    explain_main_text_choice,
    is_comment_like_text,
    is_teaser_like_text,
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

    def test_structured_extraction_rejects_social_meta_teaser_when_richer_body_exists(self) -> None:
        html = """
        <html><body>
          <script type="application/json">
            {
              "pages": {
                "socialMetaData": {
                  "description": "Today, we have taller box jumps paired with heavy hang power cleans."
                },
                "post": {
                  "content": "Workout of the Day\\n8 rounds for time of:\\n5 hang power cleans (135 lb)\\n7 box jumps\\nCompare to 2025-04-03"
                }
              }
            }
          </script>
        </body></html>
        """
        info = explain_main_text_choice(html)
        text = extract_main_text_from_html(html)
        self.assertEqual(info["source_type"], "structured_json")
        self.assertIn("post.content", info["selector"])
        self.assertIn("8 rounds for time", text)
        self.assertNotIn("Today, we have", text)

    def test_dom_workout_wins_over_structured_teaser(self) -> None:
        html = """
        <html><body>
          <script type="application/json">
            {"socialMetaData": {"description": "Today, we have a fast sprint workout."}}
          </script>
          <main>
            <article class="entry-content">
              <h2>Workout of the Day</h2>
              <p>5 rounds for time of:</p>
              <p>400-meter run</p>
              <p>15 burpees</p>
            </article>
          </main>
        </body></html>
        """
        info = explain_main_text_choice(html)
        text = extract_main_text_from_html(html)
        self.assertEqual(info["source_type"], "dom")
        self.assertIn("5 rounds for time", text)
        self.assertNotIn("Today, we have", text)

    def test_teaser_like_text_detector(self) -> None:
        self.assertTrue(is_teaser_like_text("Today, we have a challenging couplet to test pacing."))
        self.assertFalse(is_teaser_like_text("Workout of the Day\n5 rounds for time of:\n400 m run\n15 burpees"))

    def test_classify_page_marks_structured_prescription_as_wod(self) -> None:
        html = """
        <html><body><main>
          <article>
            <h2>Workout of the Day</h2>
            <p>8 rounds for time of:</p>
            <p>5 hang power cleans (135 lb)</p>
            <p>7 box jumps</p>
          </article>
        </main></body></html>
        """
        soup = BeautifulSoup(html, "lxml")
        text = extract_main_text_from_html(html)
        self.assertEqual(classify_page(soup, text), "wod")

    def test_movement_alias_detection(self) -> None:
        movements = detect_movements("5 rounds for time of: 10 handstand push-ups and 15 wall ball shots")
        norms = {entry["movement_norm"] for entry in movements}
        self.assertIn("handstand_push_up", norms)
        self.assertIn("wall_ball", norms)

    def test_measurement_extraction_with_si_normalization(self) -> None:
        entities = extract_measurements("Deadlift 225 lb, Run 400 m, 21 reps")
        load = next(e for e in entities if e.get("kind") == "load")
        distance = next(e for e in entities if e.get("kind") == "distance")
        reps = next(e for e in entities if e.get("kind") == "reps")
        self.assertAlmostEqual(load["value_si"], 102.058, places=2)
        self.assertEqual(load["unit_si"], "kg")
        self.assertEqual(distance["value_si"], 400.0)
        self.assertEqual(distance["unit_si"], "m")
        self.assertEqual(reps["unit_si"], "reps")

    def test_workout_format_inference_strength_skill(self) -> None:
        fmt = detect_workout_format("Build to a heavy snatch. 5-5-5-5-5")
        self.assertEqual(fmt, "strength_skill")

    def test_wod_block_scorer_rejects_comment_like_block(self) -> None:
        score_comment, _ = score_wod_block("Yesterday I did this RX. Reply")
        score_wod, _ = score_wod_block("8 rounds for time of:\n5 power cleans (135 lb)\n7 burpees")
        self.assertLess(score_comment, score_wod)

    def test_select_main_wod_block_prefers_structured_block_over_teaser(self) -> None:
        raw_text = (
            "Today, we have a great challenge for everyone.\n\n"
            "Workout of the Day\n"
            "8 rounds for time of:\n"
            "5 power cleans (135 lb)\n"
            "7 box jumps\n"
            "Compare to 2025-04-03"
        )
        block, ambiguous, score, reasons = select_main_wod_block(raw_text)
        self.assertIsNotNone(block)
        self.assertFalse(ambiguous)
        self.assertGreater(score, 5)
        self.assertIn("8 rounds for time", block or "")
        self.assertTrue(any("measurement" in reason or "format" in reason for reason in reasons))

    def test_parse_one_ambiguous_editorial_stays_needs_review(self) -> None:
        row = {
            "wod_date": "2026-03-14",
            "resolved_url": "https://example.com",
            "page_type": "wod",
            "raw_text": "Today, we have a great workout for all levels. Subscribe for more.",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "needs_review")

    def test_parse_one_promotes_unknown_for_time_to_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-04-03",
            "resolved_url": "https://www.crossfit.com/workout/2026/04/03",
            "page_type": "unknown",
            "raw_text": (
                "Workout of the Day\n"
                "8 rounds for time of:\n"
                "5 hang power cleans (135 lb)\n"
                "7 box jumps\n"
                "Compare to 2025-04-03"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "for_time")

    def test_parse_one_promotes_unknown_rest_day_to_valid_rest_day(self) -> None:
        row = {
            "wod_date": "2026-04-02",
            "resolved_url": "https://www.crossfit.com/workout/2026/04/02",
            "page_type": "unknown",
            "raw_text": "Workout of the Day\nRest Day",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_rest_day")
        self.assertEqual(payload["is_rest_day"], 1)

    def test_parse_one_teaser_only_stays_needs_review(self) -> None:
        row = {
            "wod_date": "2026-03-09",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/09",
            "page_type": "unknown",
            "raw_text": "Today, we have a fun challenge for all levels.",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "needs_review")

    def test_parse_one_promotes_unknown_strength_skill_to_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-03-25",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/25",
            "page_type": "unknown",
            "raw_text": (
                "Workout of the Day\n"
                "Build to a heavy snatch\n"
                "5-5-5-5-5 overhead squat (95 lb)"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "strength_skill")

    def test_parse_one_promo_cta_is_editorial_ignored(self) -> None:
        row = {
            "wod_date": "2026-03-10",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/10",
            "page_type": "unknown",
            "raw_text": "Check Out the Open Leaderboard\nWatch the 26.3 Recap\nRead More",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "editorial_ignored")

    def test_parse_one_structured_strength_skill_emom_is_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-03-23",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/23",
            "page_type": "unknown",
            "raw_text": (
                "Workout of the Day\n"
                "Every 5 minutes for 7 sets, for load:\n"
                "2 hang power snatch\n"
                "2 overhead squat"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "strength_skill")

    def test_parse_one_rest_day_still_valid_rest_day(self) -> None:
        row = {
            "wod_date": "2026-04-02",
            "resolved_url": "https://www.crossfit.com/workout/2026/04/02",
            "page_type": "unknown",
            "raw_text": "Workout of the Day\nRest Day",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_rest_day")
        entities = json.loads(payload["movement_list_json"])
        movement_entities = [e for e in entities if e.get("kind") == "movement"]
        self.assertEqual(movement_entities, [])

    def test_parse_one_for_time_metcon_still_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-04-03",
            "resolved_url": "https://www.crossfit.com/workout/2026/04/03",
            "page_type": "unknown",
            "raw_text": "Workout of the Day\n5 rounds for time of:\n10 burpees\n200 m run",
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")

    def test_parse_one_cta_and_richer_wod_block_prefers_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-03-20",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/20",
            "page_type": "unknown",
            "raw_text": (
                "Learn the Movement →\nRead More\n\n"
                "Workout of the Day\n"
                "5 rounds for time of:\n"
                "10 thrusters (95 lb)\n"
                "200 m run"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "for_time")

    def test_parse_one_strength_skill_with_competing_cta_is_valid_wod(self) -> None:
        row = {
            "wod_date": "2026-03-23",
            "resolved_url": "https://www.crossfit.com/workout/2026/03/23",
            "page_type": "unknown",
            "raw_text": (
                "Check Out the Open Leaderboard\n\n"
                "Workout of the Day\n"
                "Every 5 minutes for 7 sets, for load:\n"
                "2 hang power snatch\n"
                "2 overhead squat"
            ),
        }
        payload = parse_one(row)
        self.assertEqual(payload["record_status"], "valid_wod")
        self.assertEqual(payload["workout_format"], "strength_skill")

    def test_extract_ordered_movements_for_time_sequence(self) -> None:
        items = extract_ordered_movements("5 rounds for time of:\n10 thrusters (95 lb)\n200 m run")
        ids = [item["movement_id"] for item in items]
        self.assertEqual(ids[:2], ["thruster", "run"])
        self.assertEqual(items[0]["reps"], 10)

    def test_compact_rounds_structure_two_movements_only(self) -> None:
        items = extract_ordered_movements("8 rounds for time of: 5 box jump-overs, 5 hang power cleans")
        ids = [item["movement_id"] for item in items]
        self.assertEqual(ids, ["box_jump_over", "hang_power_clean"])
        self.assertEqual(items[0]["rounds"], 8)
        self.assertEqual(len(items), 2)

    def test_extract_ordered_movements_strength_skill_sequence(self) -> None:
        items = extract_ordered_movements("Every 5 minutes for 7 sets:\n3 push presses\n2 push jerks\n1 split jerk")
        ids = [item["movement_id"] for item in items]
        self.assertEqual(ids, ["push_press", "push_jerk", "split_jerk"])

    def test_specificity_beats_generic_clean_and_box(self) -> None:
        items = extract_ordered_movements("5 box jump-overs and 5 hang power cleans")
        ids = [item["movement_id"] for item in items]
        self.assertIn("box_jump_over", ids)
        self.assertIn("hang_power_clean", ids)
        self.assertNotIn("box_jump", ids)
        self.assertNotIn("clean", ids)
        self.assertNotIn("power_clean", ids)

    def test_detect_workout_format_emom_amrap_tabata(self) -> None:
        self.assertEqual(detect_workout_format("EMOM 20: 5 burpees"), "emom")
        self.assertEqual(detect_workout_format("15-minute AMRAP of 10 pull-ups"), "amrap")
        self.assertEqual(detect_workout_format("Tabata air squats"), "tabata")

    def test_male_female_variant_load_parsing(self) -> None:
        items = extract_ordered_movements("Wall-ball shots 20/14 lb")
        self.assertTrue(items)
        self.assertEqual(items[0]["sex_variant"], "male_female")

    def test_compare_to_is_extracted(self) -> None:
        row = {
            "wod_date": "2026-04-01",
            "resolved_url": "https://example.com",
            "page_type": "unknown",
            "raw_text": "Workout of the Day\n5 rounds for time of:\n10 burpees\nCompare to 2025-04-01",
        }
        payload = parse_one(row)
        self.assertIn("Compare to", payload["compare_to_text"] or "")

    def test_promo_page_does_not_generate_fake_movements(self) -> None:
        row = {
            "wod_date": "2026-03-11",
            "resolved_url": "https://example.com",
            "page_type": "unknown",
            "raw_text": "Learn the Movement\nWatch the Replay\nRead More",
        }
        payload = parse_one(row)
        entities = json.loads(payload["movement_list_json"])
        movement_entities = [e for e in entities if e.get("kind") == "movement"]
        self.assertEqual(payload["record_status"], "editorial_ignored")
        self.assertEqual(len(movement_entities), 0)

    def test_inferred_rx_fallback_applied_only_when_source_absent(self) -> None:
        items = extract_ordered_movements("Box jump")
        self.assertTrue(items[0]["rx_standard_applied"])
        self.assertIn("inferred_male", items[0])

    def test_explicit_source_overrides_inferred_defaults(self) -> None:
        items = extract_ordered_movements("Box jump 24 in")
        self.assertFalse(items[0]["rx_standard_applied"])
        self.assertEqual(items[0]["distance_unit"], "in")


if __name__ == "__main__":
    unittest.main()
