from __future__ import annotations

import argparse
import json
import re

from .db import get_conn

MOVEMENT_PATTERNS = [
    "squat", "deadlift", "clean", "jerk", "snatch", "thruster", "pull-up", "push-up",
    "burpee", "run", "row", "double-under", "toes-to-bar", "muscle-up", "wall-ball",
]

FORMAT_PATTERNS = {
    "amrap": re.compile(r"\bamrap\b", re.IGNORECASE),
    "for_time": re.compile(r"\bfor time\b", re.IGNORECASE),
    "emom": re.compile(r"\bemom\b", re.IGNORECASE),
    "tabata": re.compile(r"\btabata\b", re.IGNORECASE),
}

RPE_PATTERN = re.compile(r"\brpe\s*[:\-]?\s*(\d{1,2}(?:\.\d)?)", re.IGNORECASE)
LOAD_PATTERN = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s?(?P<unit>kg|kgs|lb|lbs|pood|poods)\b", re.IGNORECASE)
DISTANCE_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s?(?P<unit>m|meter|meters|metre|metres|km|mi|mile|miles|yd|yard|yards|ft|foot|feet)\b",
    re.IGNORECASE,
)
STOP_BLOCK_MARKERS = ("related", "comments", "share", "podcast", "newsletter", "watch")


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


def extract_notes(text: str) -> str | None:
    note_lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and any(marker in line.lower() for marker in ["note", "scaling", "tips", "modify"])
    ]
    if not note_lines:
        return None
    return "\n".join(note_lines)


def detect_workout_format(text: str) -> str | None:
    for name, pattern in FORMAT_PATTERNS.items():
        if pattern.search(text):
            return name
    return None


def extract_rpe_source(text: str) -> str | None:
    match = RPE_PATTERN.search(text)
    if not match:
        return None
    return f"RPE {match.group(1)}"


def extract_measurements(text: str) -> list[dict]:
    entries: list[dict] = []
    for match in LOAD_PATTERN.finditer(text):
        entries.append(
            {
                "kind": "load",
                "value_source": float(match.group("value")),
                "unit_source": match.group("unit").lower(),
                "context": match.group(0),
            }
        )
    for match in DISTANCE_PATTERN.finditer(text):
        entries.append(
            {
                "kind": "distance",
                "value_source": float(match.group("value")),
                "unit_source": match.group("unit").lower(),
                "context": match.group(0),
            }
        )
    return entries


def extract_wod_block(raw_text: str) -> tuple[str | None, bool]:
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return None, True

    start_idx = None
    for idx, line in enumerate(lines):
        if any(pattern.search(line.lower()) for pattern in FORMAT_PATTERNS.values()):
            start_idx = idx
            break

    if start_idx is None:
        return None, True

    block: list[str] = []
    for line in lines[start_idx:start_idx + 25]:
        line_low = line.lower()
        if any(marker in line_low for marker in STOP_BLOCK_MARKERS) and len(block) >= 2:
            break
        block.append(line)

    wod_block = "\n".join(block).strip()
    has_measure_or_movement = bool(extract_measurements(wod_block) or detect_movements(wod_block))
    is_ambiguous = len(block) < 2 or not has_measure_or_movement
    if not wod_block:
        return None, True
    return wod_block, is_ambiguous


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

    parse_text = raw_text
    if row["page_type"] == "wod":
        wod_block, ambiguous_wod = extract_wod_block(raw_text)
        if wod_block:
            wod_text = wod_block
            parse_text = wod_block
        if ambiguous_wod:
            record_status = "needs_review"

    movements = detect_movements(parse_text)
    measurements = extract_measurements(parse_text)
    workout_format = detect_workout_format(parse_text)
    rpe_source = extract_rpe_source(parse_text)

    tags = []
    if is_rest_day:
        tags.append("rest_day")
    if is_editorial_only:
        tags.append("editorial_only")
    if movements:
        tags.append("has_movements")
    if measurements:
        tags.append("has_measurements")
    if workout_format:
        tags.append(f"format:{workout_format}")
    if record_status == "needs_review":
        tags.append("needs_review")

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
        "notes_text": extract_notes(parse_text),
        "score_text": None,
        "compare_to_text": None,
        "rpe_source": rpe_source,
        "workout_format": workout_format,
        "movement_list_json": json.dumps(movements + measurements, ensure_ascii=False),
        "tags_json": json.dumps(tags, ensure_ascii=False),
    }


def upsert_movements(conn, wod_date: str, entities_json: str) -> None:
    entities = json.loads(entities_json or "[]")
    conn.execute("DELETE FROM movements WHERE wod_date = ?", (wod_date,))
    for entity in entities:
        if entity.get("kind") == "load":
            conn.execute(
                """
                INSERT INTO movements (wod_date, load_value_source, load_unit_source, context_text)
                VALUES (?, ?, ?, ?)
                """,
                (
                    wod_date,
                    entity.get("value_source"),
                    entity.get("unit_source"),
                    entity.get("context"),
                ),
            )
        elif entity.get("kind") == "distance":
            conn.execute(
                """
                INSERT INTO movements (wod_date, distance_value_source, distance_unit_source, context_text)
                VALUES (?, ?, ?, ?)
                """,
                (
                    wod_date,
                    entity.get("value_source"),
                    entity.get("unit_source"),
                    entity.get("context"),
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO movements (wod_date, movement_raw, movement_norm, context_text)
                VALUES (?, ?, ?, ?)
                """,
                (
                    wod_date,
                    entity.get("movement_raw"),
                    entity.get("movement_norm"),
                    entity.get("movement_raw"),
                ),
            )


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
                        rpe_source, workout_format, movement_list_json, tags_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                        rpe_source=excluded.rpe_source,
                        workout_format=excluded.workout_format,
                        movement_list_json=excluded.movement_list_json,
                        tags_json=excluded.tags_json,
                        last_updated_at=CURRENT_TIMESTAMP
                    """,
                    (
                        payload["wod_date"], payload["source_url"], payload["record_status"], payload["page_type"],
                        payload["is_rest_day"], payload["is_missing"], payload["is_editorial_only"], payload["title"],
                        payload["wod_text"], payload["notes_text"], payload["score_text"], payload["compare_to_text"],
                        payload["rpe_source"], payload["workout_format"], payload["movement_list_json"], payload["tags_json"],
                    ),
                )
                upsert_movements(conn, payload["wod_date"], payload["movement_list_json"])
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
