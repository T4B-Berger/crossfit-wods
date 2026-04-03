from __future__ import annotations

import argparse
import json
import re

from .db import get_conn

MOVEMENT_PATTERNS = [
    "squat", "deadlift", "clean", "jerk", "snatch", "thruster", "pull-up", "push-up",
    "burpee", "run", "row", "double-under", "toes-to-bar", "muscle-up", "wall-ball",
]


def detect_movements(text: str) -> list[dict]:
    found: list[dict] = []
    low = text.lower()
    for movement in MOVEMENT_PATTERNS:
        if movement in low:
            found.append({"movement_raw": movement, "movement_norm": movement})
    return found


def extract_title(text: str) -> str | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return lines[0][:200] if lines else None


def classify_record(page_type: str, raw_text: str | None) -> tuple[str, int, int, int, str | None]:
    if page_type == "not_found":
        return "missing_page", 0, 1, 0, None
    if page_type == "rest_day":
        return "valid_rest_day", 1, 0, 0, None
    if page_type == "editorial_only":
        return "editorial_ignored", 0, 0, 1, None
    if page_type == "wod":
        return "valid_wod", 0, 0, 0, raw_text
    return "needs_review", 0, 0, 0, raw_text


def parse_one(row) -> dict:
    raw_text = row["raw_text"] or ""
    record_status, is_rest_day, is_missing, is_editorial_only, wod_text = classify_record(row["page_type"], raw_text)
    movements = detect_movements(raw_text)
    tags = []
    if is_rest_day:
        tags.append("rest_day")
    if is_editorial_only:
        tags.append("editorial_only")
    if movements:
        tags.append("has_movements")
    return {
        "wod_date": row["wod_date"],
        "source_url": row["resolved_url"],
        "record_status": record_status,
        "page_type": row["page_type"],
        "is_rest_day": is_rest_day,
        "is_missing": is_missing,
        "is_editorial_only": is_editorial_only,
        "title": extract_title(raw_text),
        "wod_text": wod_text,
        "notes_text": None,
        "score_text": None,
        "compare_to_text": None,
        "movement_list_json": json.dumps(movements, ensure_ascii=False),
        "tags_json": json.dumps(tags, ensure_ascii=False),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()

    with get_conn(args.db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM daily_pages
            WHERE fetch_status IN ('success', 'not_found')
              AND parse_status = 'pending'
            ORDER BY wod_date ASC
            LIMIT ?
            """,
            (args.limit,),
        ).fetchall()

        for row in rows:
            try:
                payload = parse_one(row)
                conn.execute(
                    """
                    INSERT INTO daily_wods (
                        wod_date, source_url, record_status, page_type, is_rest_day, is_missing,
                        is_editorial_only, title, wod_text, notes_text, score_text, compare_to_text,
                        movement_list_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(wod_date) DO UPDATE SET
                        source_url=excluded.source_url,
                        record_status=excluded.record_status,
                        page_type=excluded.page_type,
                        is_rest_day=excluded.is_rest_day,
                        is_missing=excluded.is_missing,
                        is_editorial_only=excluded.is_editorial_only,
                        title=excluded.title,
                        wod_text=excluded.wod_text,
                        notes_text=excluded.notes_text,
                        score_text=excluded.score_text,
                        compare_to_text=excluded.compare_to_text,
                        movement_list_json=excluded.movement_list_json,
                        tags_json=excluded.tags_json,
                        last_updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        payload["wod_date"], payload["source_url"], payload["record_status"], payload["page_type"],
                        payload["is_rest_day"], payload["is_missing"], payload["is_editorial_only"], payload["title"],
                        payload["wod_text"], payload["notes_text"], payload["score_text"], payload["compare_to_text"],
                        payload["movement_list_json"], payload["tags_json"],
                    ),
                )
                conn.execute(
                    "UPDATE daily_pages SET parse_status = 'parsed', parse_error = NULL WHERE wod_date = ?",
                    (payload["wod_date"],),
                )
            except Exception as exc:
                conn.execute(
                    "UPDATE daily_pages SET parse_status = 'error', parse_error = ? WHERE wod_date = ?",
                    (str(exc), row["wod_date"]),
                )
            conn.commit()
            print(f"parsed {row['wod_date']}")


if __name__ == "__main__":
    main()
