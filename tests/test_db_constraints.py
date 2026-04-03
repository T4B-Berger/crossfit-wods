from __future__ import annotations

import sqlite3
import tempfile
import unittest
from pathlib import Path

from crossfit_wods.db import init_db, get_conn


class DbStatusConstraintTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmpdir.name) / "test.sqlite"
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_daily_pages_rejects_invalid_fetch_status(self) -> None:
        with get_conn(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO daily_pages (wod_date, expected_url, fetch_status, page_type, parse_status)
                    VALUES ('2024-01-01', 'https://example.com', 'bad_status', 'unknown', 'pending')
                    """
                )

    def test_daily_wods_rejects_invalid_record_status(self) -> None:
        with get_conn(self.db_path) as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute(
                    """
                    INSERT INTO daily_wods (wod_date, record_status, page_type)
                    VALUES ('2024-01-01', 'bad_record', 'wod')
                    """
                )

    def test_rpe_inference_method_column_exists(self) -> None:
        with get_conn(self.db_path) as conn:
            cols = {row["name"] for row in conn.execute("PRAGMA table_info(daily_wods)")}
        self.assertIn("rpe_inference_method", cols)


if __name__ == "__main__":
    unittest.main()
