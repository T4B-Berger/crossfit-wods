from __future__ import annotations

import argparse
import json
import sqlite3


def print_counts(conn: sqlite3.Connection, start: str, end: str) -> None:
    print("=== page_type counts ===")
    for row in conn.execute(
        """
        SELECT page_type, COUNT(*) c
        FROM daily_pages
        WHERE wod_date BETWEEN ? AND ?
        GROUP BY page_type
        ORDER BY c DESC
        """,
        (start, end),
    ):
        print(dict(row))

    print("\n=== record_status counts ===")
    for row in conn.execute(
        """
        SELECT record_status, COUNT(*) c
        FROM daily_wods
        WHERE wod_date BETWEEN ? AND ?
        GROUP BY record_status
        ORDER BY c DESC
        """,
        (start, end),
    ):
        print(dict(row))

    print("\n=== workout_format counts ===")
    for row in conn.execute(
        """
        SELECT workout_format, COUNT(*) c
        FROM daily_wods
        WHERE wod_date BETWEEN ? AND ?
        GROUP BY workout_format
        ORDER BY c DESC
        """,
        (start, end),
    ):
        print(dict(row))


def print_samples(conn: sqlite3.Connection, start: str, end: str, status: str, limit: int) -> None:
    print(f"\n=== sample {status} ===")
    rows = conn.execute(
        """
        SELECT wod_date, page_type, record_status, workout_format, substr(wod_text,1,220) preview, tags_json
        FROM daily_wods
        WHERE wod_date BETWEEN ? AND ? AND record_status = ?
        ORDER BY wod_date
        LIMIT ?
        """,
        (start, end, status, limit),
    ).fetchall()
    for row in rows:
        payload = dict(row)
        try:
            payload["tags"] = json.loads(payload.pop("tags_json") or "[]")[:8]
        except json.JSONDecodeError:
            payload["tags"] = []
        print(payload)


def print_debug_dates(conn: sqlite3.Connection, dates: list[str]) -> None:
    print("\n=== debug dates ===")
    for d in dates:
        row = conn.execute(
            """
            SELECT wod_date, page_type, record_status, workout_format, substr(wod_text,1,260) preview, tags_json
            FROM daily_wods WHERE wod_date = ?
            """,
            (d,),
        ).fetchone()
        if not row:
            print({"wod_date": d, "missing": True})
            continue
        payload = dict(row)
        try:
            payload["tags"] = json.loads(payload.pop("tags_json") or "[]")
        except json.JSONDecodeError:
            payload["tags"] = []
        print(payload)


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit parser output over a date window")
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--sample-limit", type=int, default=5)
    parser.add_argument("--debug-dates", nargs="*", default=[])
    args = parser.parse_args()

    conn = sqlite3.connect(args.db_path)
    conn.row_factory = sqlite3.Row

    print_counts(conn, args.start_date, args.end_date)
    for status in ["valid_wod", "needs_review", "editorial_ignored"]:
        print_samples(conn, args.start_date, args.end_date, status, args.sample_limit)
    if args.debug_dates:
        print_debug_dates(conn, args.debug_dates)


if __name__ == "__main__":
    main()
