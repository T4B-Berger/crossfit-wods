from __future__ import annotations

import argparse
import json
import re

from .db import get_conn

MOVEMENT_ALIASES = {
    "pull-up": ("pull-up", "pull up", "pullups", "pullups"),
    "push-up": ("push-up", "push up", "pushups", "pushups"),
    "air squat": ("air squat", "air squats"),
    "double-under": ("double-under", "double under", "double unders"),
    "knees-to-elbows": ("knees-to-elbows", "knees to elbows", "knees-to-elbow"),
    "clean-and-jerk": ("clean and jerk", "clean-and-jerk"),
    "snatch": ("snatch",),
    "thruster": ("thruster", "thrusters"),
    "deadlift": ("deadlift", "deadlifts"),
    "row": ("row", "rowing"),
    "run": ("run", "running"),
    "burpee": ("burpee", "burpees"),
    "box jump": ("box jump", "box jumps"),
    "wall-ball shot": ("wall ball", "wall-ball", "wall ball shot", "wall-ball shot"),
    "toes-to-bar": ("toes-to-bar", "toes to bar"),
    "muscle-up": ("muscle-up", "muscle up", "muscleups"),
    "sit-up": ("sit-up", "sit up", "situps"),
    "handstand push-up": ("handstand push-up", "handstand push-ups", "handstand push up", "handstand push ups", "hspu"),
    "walking lunge": ("walking lunge", "walking lunges"),
    "lunge": ("lunge", "lunges"),
    "power clean": ("power clean", "power cleans"),
    "power snatch": ("power snatch", "power snatches"),
    "overhead squat": ("overhead squat", "overhead squats"),
    "front squat": ("front squat", "front squats"),
    "back squat": ("back squat", "back squats"),
    "sumo deadlift high pull": ("sumo deadlift high pull", "sdlhp"),
    "clean": ("clean", "cleans"),
    "jerk": ("jerk", "jerks"),
    "squat": ("squat", "squats"),
}

FORMAT_PATTERNS = {
    "amrap": re.compile(r"\bamrap\b", re.IGNORECASE),
    "for_time": re.compile(r"\bfor time\b", re.IGNORECASE),
    "emom": re.compile(r"\bemom\b", re.IGNORECASE),
    "tabata": re.compile(r"\btabata\b", re.IGNORECASE),
}
COMMENT_BLOCK_RE = re.compile(r"\b(reply|leave a comment|verify email|yesterday i did|i modified)\b", re.IGNORECASE)
STRENGTH_LIFT_RE = re.compile(
    r"\b(?:back\s+squat|squat|deadlift|bench(?:-press|\s+press)?|press|clean|jerk|snatch)\b",
    re.IGNORECASE,
)
STRENGTH_KEYWORD_RE = re.compile(
    r"\b(?:find\s+your\s+best|best\s+\w+|build\s+to\s+a\s+heavy|every\s+\d+\s+minutes?|"
    r"1\s*rep|3\s*reps|5\s*reps|5\s*,\s*3\s*,\s*(?:and\s*)?1\s*reps|"
    r"(?:1|3|5)\s*[-x]\s*(?:1|3|5)\s*[-x]\s*(?:1|3|5))\b",
    re.IGNORECASE,
)
STRENGTH_SCHEME_RE = re.compile(r"\b(?:1-1-1-1-1|3-3-3-3-3|5-5-5-5-5|\d+\s*sets?\s+of\s+\d+)\b", re.IGNORECASE)

RPE_PATTERN = re.compile(r"\brpe\s*[:\-]?\s*(\d{1,2}(?:\.\d)?)", re.IGNORECASE)
LOAD_PATTERN = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s?(?P<unit>kg|kgs|lb|lbs|pood|poods)\b", re.IGNORECASE)
DISTANCE_PATTERN = re.compile(
    r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(?P<unit>m|meter|meters|metre|metres|km|mi|mile|miles|yd|yard|yards|ft|foot|feet|inch|in)\b",
    re.IGNORECASE,
)
REPS_PATTERN = re.compile(r"\b(?P<value>\d+)\s*reps?\b", re.IGNORECASE)
WOD_STRUCTURE_RE = re.compile(r"(^|\s)(\d+(?:\s*[-x]\s*\d+)+|\d+\s*rounds?)", re.IGNORECASE)
STRUCTURE_RE = re.compile(r"\b(?:for time|each for time|amrap|emom|tabata|\d+\s*rounds?)\b", re.IGNORECASE)
MEASURABLE_REPS_RE = re.compile(r"\b(?:\d+(?:\s*[-x]\s*\d+)+|\d+)\s*reps?\b", re.IGNORECASE)
MEASURABLE_TIME_RE = re.compile(r"\b\d+\s*(?:sec(?:ond)?s?|min(?:ute)?s?|hours?)\b|\b\d+\s*:\s*\d+\b", re.IGNORECASE)
STOP_BLOCK_MARKERS = ("related", "comments", "share", "podcast", "newsletter", "watch")
EDITORIAL_LINE_MARKERS = ("resource", "resources", "read", "article", "link")


def split_into_blocks(raw_text: str) -> list[str]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n+", raw_text) if chunk.strip()]
    if chunks:
        return chunks
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []
    blocks: list[str] = []
    current: list[str] = []
    for line in lines:
        if any(marker in line.lower() for marker in STOP_BLOCK_MARKERS) and current:
            blocks.append("\n".join(current))
            current = []
            continue
        current.append(line)
        if len(current) >= 6:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def _normalize_load_to_kg(value: float, unit: str) -> tuple[float, str]:
    u = unit.lower()
    if u in {"kg", "kgs"}:
        return value, "kg"
    if u in {"lb", "lbs"}:
        return round(value * 0.45359237, 3), "kg"
    if u in {"pood", "poods"}:
        return round(value * 16.3807, 3), "kg"
    return value, "kg"


def _normalize_distance_to_m(value: float, unit: str) -> tuple[float, str]:
    u = unit.lower()
    if u in {"m", "meter", "meters", "metre", "metres"}:
        return value, "m"
    if u == "km":
        return value * 1000.0, "m"
    if u in {"mi", "mile", "miles"}:
        return round(value * 1609.344, 3), "m"
    if u in {"yd", "yard", "yards"}:
        return round(value * 0.9144, 3), "m"
    if u in {"ft", "foot", "feet"}:
        return round(value * 0.3048, 3), "m"
    if u in {"inch", "in"}:
        return round(value * 0.0254, 3), "m"
    return value, "m"


def is_strength_line(text: str) -> bool:
    line = text.lower()
    return bool(STRENGTH_LIFT_RE.search(line) and STRENGTH_KEYWORD_RE.search(line))


def detect_movements(text: str) -> list[dict]:
    found: list[dict] = []
    seen: set[str] = set()
    low = text.lower()
    for movement_norm, aliases in MOVEMENT_ALIASES.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", low):
                if movement_norm in seen:
                    break
                seen.add(movement_norm)
                found.append({"movement_raw": alias, "movement_norm": movement_norm})
                break
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


def extract_compare_to(text: str) -> str | None:
    for line in text.splitlines():
        if "compare to" in line.lower():
            return line.strip()
    return None


def detect_workout_format(text: str) -> str | None:
    low = text.lower()
    if "rest day" in low:
        return "rest_day"
    if "build to a heavy" in low or STRENGTH_SCHEME_RE.search(text) or "every" in low and "minutes" in low:
        return "strength_skill"
    if is_strength_line(text):
        return "strength"
    for name, pattern in FORMAT_PATTERNS.items():
        if pattern.search(text):
            return name
    if STRUCTURE_RE.search(text) and detect_movements(text):
        return "mixed"
    return None


def extract_rpe_source(text: str) -> str | None:
    match = RPE_PATTERN.search(text)
    if not match:
        return None
    return f"RPE {match.group(1)}"


def extract_measurements(text: str) -> list[dict]:
    entries: list[dict] = []
    for match in LOAD_PATTERN.finditer(text):
        value_source = float(match.group("value"))
        unit_source = match.group("unit").lower()
        value_si, unit_si = _normalize_load_to_kg(value_source, unit_source)
        entries.append(
            {
                "kind": "load",
                "value_source": value_source,
                "unit_source": unit_source,
                "value_si": value_si,
                "unit_si": unit_si,
                "context": match.group(0),
            }
        )
    for match in DISTANCE_PATTERN.finditer(text):
        value_source = float(match.group("value"))
        unit_source = match.group("unit").lower()
        value_si, unit_si = _normalize_distance_to_m(value_source, unit_source)
        entries.append(
            {
                "kind": "distance",
                "value_source": value_source,
                "unit_source": unit_source,
                "value_si": value_si,
                "unit_si": unit_si,
                "context": match.group(0),
            }
        )
    for match in REPS_PATTERN.finditer(text):
        entries.append(
            {
                "kind": "reps",
                "value_source": float(match.group("value")),
                "unit_source": "reps",
                "value_si": float(match.group("value")),
                "unit_si": "reps",
                "context": match.group(0),
            }
        )
    return entries


def has_measurable_quantity(text: str) -> bool:
    if MEASURABLE_REPS_RE.search(text) or MEASURABLE_TIME_RE.search(text):
        return True
    return any(entry.get("kind") in {"distance", "load", "reps"} for entry in extract_measurements(text))


def score_wod_block(text: str) -> tuple[int, list[str]]:
    low = text.lower()
    score = 0
    reasons: list[str] = []

    marker_hits = sum(1 for marker in ["for time", "amrap", "tabata", "emom", "rounds for time", "21-15-9", "time cap", "compare to"] if marker in low)
    if marker_hits:
        score += marker_hits * 3
        reasons.append(f"format markers={marker_hits}")

    movement_hits = len(detect_movements(text))
    if movement_hits:
        score += min(10, movement_hits * 2)
        reasons.append(f"movement hits={movement_hits}")

    measurement_hits = len(extract_measurements(text))
    if measurement_hits:
        score += min(10, measurement_hits)
        reasons.append(f"measurement hits={measurement_hits}")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    short_lines = [line for line in lines if 4 <= len(line) <= 90]
    if len(short_lines) >= 3:
        score += 4
        reasons.append("multiple short prescription lines")

    if STRENGTH_SCHEME_RE.search(text) or is_strength_line(text):
        score += 6
        reasons.append("strength/skill pattern")

    if COMMENT_BLOCK_RE.search(text):
        score -= 12
        reasons.append("comment-like markers")

    if any(term in low for term in ["previous post", "next post", "verify email", "subscribe"]):
        score -= 8
        reasons.append("site/chrome noise")

    return score, reasons


def select_main_wod_block(raw_text: str) -> tuple[str | None, bool, int, list[str]]:
    blocks = split_into_blocks(raw_text)
    if not blocks:
        return None, True, -999, ["no blocks"]

    best_block: str | None = None
    best_score = -999
    best_reasons: list[str] = []

    for block in blocks:
        score, reasons = score_wod_block(block)
        if score > best_score:
            best_block = block
            best_score = score
            best_reasons = reasons

    if not best_block:
        return None, True, -999, ["no best block"]

    # Trim tail noise for strength/editorial blends.
    trimmed_lines: list[str] = []
    seen_strength = False
    for line in [ln.strip() for ln in best_block.splitlines() if ln.strip()]:
        line_low = line.lower()
        if seen_strength and (
            "http://" in line_low
            or "https://" in line_low
            or "www." in line_low
            or any(marker in line_low for marker in EDITORIAL_LINE_MARKERS)
            or COMMENT_BLOCK_RE.search(line_low)
        ):
            break
        trimmed_lines.append(line)
        seen_strength = seen_strength or is_strength_line(line)
    best_block = "\n".join(trimmed_lines).strip()

    has_structure = bool(STRUCTURE_RE.search(best_block) or WOD_STRUCTURE_RE.search(best_block) or is_strength_line(best_block) or STRENGTH_SCHEME_RE.search(best_block))
    has_movement = bool(detect_movements(best_block))
    has_measurable = has_measurable_quantity(best_block)
    ambiguous = not (has_structure and has_movement and has_measurable) or best_score < 5
    return best_block, ambiguous, best_score, best_reasons


def extract_wod_block(raw_text: str) -> tuple[str | None, bool]:
    block, ambiguous, _, _ = select_main_wod_block(raw_text)
    return block, ambiguous


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
    block_score = None
    block_reasons: list[str] = []
    if row["page_type"] == "wod":
        wod_block, ambiguous_wod, block_score, block_reasons = select_main_wod_block(raw_text)
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
    if block_score is not None:
        tags.append(f"block_score:{block_score}")
    for reason in block_reasons[:4]:
        tags.append(f"block_reason:{reason}")
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
        "compare_to_text": extract_compare_to(parse_text),
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
