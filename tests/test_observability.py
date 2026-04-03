from __future__ import annotations

import unittest
from tempfile import TemporaryDirectory

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

    def test_build_quality_metrics_uses_stable_string_value_schema(self) -> None:
        quality = build_quality_metrics(pd.DataFrame(), pd.DataFrame(), pd.DataFrame())
        self.assertIn("value_type", quality.columns)
        self.assertTrue(all(pd.isna(value) or isinstance(value, str) for value in quality["value"]))

    def test_build_quality_metrics_parquet_export_with_mixed_logical_types(self) -> None:
        wods = pd.DataFrame([{"wod_date": "2024-01-01", "record_status": "valid_wod"}])
        pages = pd.DataFrame([{"wod_date": "2024-01-01", "fetch_status": "success"}])
        movements = pd.DataFrame()
        quality = build_quality_metrics(wods, pages, movements)

        with TemporaryDirectory() as tmp:
            quality.to_parquet(f"{tmp}/quality_metrics.parquet", index=False)


if __name__ == "__main__":
    unittest.main()
