from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta
from pathlib import Path

from .db import get_conn, init_db
from .scraper import fetch_day, persist_html, build_expected_url


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def cmd_init_db(args: argparse.Namespace) -> None:
    init_db(args.db_path)
    start = date.fromisoformat(args.start_date)
    end = date.fromisoformat(args.end_date) if args.end_date else date.today()
    with get_conn(args.db_path) as conn:
        for d in daterange(start, end):
            conn.execute(
                """
                INSERT OR IGNORE INTO daily_pages (wod_date, expected_url, fetch_status, page_type, parse_status)
                VALUES (?, ?, 'pending', 'unknown', 'pending')
                """,
                (d.isoformat(), build_expected_url(d)),
            )
        conn.commit()


def cmd_scrape(args: argparse.Namespace) -> None:
    html_root = Path(args.html_root)
    html_root.mkdir(parents=True, exist_ok=True)
    with get_conn(args.db_path) as conn:
        rows = conn.execute(
            """
            SELECT wod_date FROM daily_pages
            WHERE fetch_status IN ('pending', 'timeout', 'network_error', 'http_error')
            ORDER BY wod_date ASC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()

        for row in rows:
            d = date.fromisoformat(row["wod_date"])
            result = fetch_day(d, timeout=args.timeout)
            html_path = None
            if result.html:
                html_path = persist_html(html_root, result.wod_date, result.html)
            conn.execute(
                """
                UPDATE daily_pages
                SET resolved_url = ?, fetch_status = ?, http_status = ?, content_hash = ?,
                    page_type = ?, scraped_at = ?, raw_text = ?, html_path = ?
                WHERE wod_date = ?
                """,
                (
                    result.resolved_url,
                    result.fetch_status,
                    result.http_status,
                    result.content_hash,
                    result.page_type,
                    datetime.utcnow().isoformat(timespec="seconds"),
                    result.raw_text,
                    html_path,
                    result.wod_date,
                ),
            )
            conn.commit()
            print(f"{result.wod_date}: {result.fetch_status} [{result.page_type}]")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init-db")
    p_init.add_argument("--db-path", required=True)
    p_init.add_argument("--start-date", required=True)
    p_init.add_argument("--end-date")
    p_init.set_defaults(func=cmd_init_db)

    p_scrape = sub.add_parser("scrape")
    p_scrape.add_argument("--db-path", required=True)
    p_scrape.add_argument("--html-root", default="data/raw/html")
    p_scrape.add_argument("--limit", type=int, default=100)
    p_scrape.add_argument("--timeout", type=int, default=20)
    p_scrape.set_defaults(func=cmd_scrape)
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
