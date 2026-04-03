from __future__ import annotations

import unittest

import pandas as pd

from crossfit_wods.export import build_quality_metrics


class ObservabilityTests(unittest.TestCase):
    def test_build_quality_metrics_contains_expected_keys(self) -> None:
        wods = pd.DataFrame(
            [
                {"wod_date": "2024-01-01", "record_status": "valid_wod"},
                {"wod_date": "2024-01-02", "record_status": "needs_review"},
            ]
        )
        pages = pd.DataFrame(
            [
                {"wod_date": "2024-01-01", "fetch_status": "success"},
                {"wod_date": "2024-01-02", "fetch_status": "not_found"},
            ]
        )
        movements = pd.DataFrame([{"id": 1}, {"id": 2}, {"id": 3}])

        quality = build_quality_metrics(wods, pages, movements)
        metrics = dict(zip(quality["metric"], quality["value"]))

        self.assertEqual(int(metrics["total_days"]), 2)
        self.assertEqual(int(metrics["needs_review"]), 1)
        self.assertEqual(int(metrics["fetch_success"]), 1)
        self.assertEqual(int(metrics["total_movements_rows"]), 3)
        self.assertEqual(metrics["coverage_start"], "2024-01-01")
        self.assertEqual(metrics["coverage_end"], "2024-01-02")


if __name__ == "__main__":
    unittest.main()
