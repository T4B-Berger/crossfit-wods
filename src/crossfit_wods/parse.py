from __future__ import annotations

import argparse
import json
import re

from .db import get_conn
from .movement_taxonomy import movement_index

MOVEMENT_ALIASES = {
    "pull_up": ("pull-up", "pull up", "pullups", "pullups"),
    "push_up": ("push-up", "push up", "pushups", "pushups"),
    "air_squat": ("air squat", "air squats"),
    "double_under": ("double-under", "double under", "double unders"),
    "knees_to_elbows": ("knees-to-elbows", "knees to elbows", "knees-to-elbow"),
    "clean_and_jerk": ("clean and jerk", "clean-and-jerk"),
    "snatch": ("snatch",),
    "thruster": ("thruster", "thrusters"),
    "deadlift": ("deadlift", "deadlifts"),
    "row": ("row", "rowing"),
    "run": ("run", "running"),
    "burpee": ("burpee", "burpees"),
    "box_jump": ("box jump", "box jumps"),
    "box_jump_over": ("box jump over", "box jump-over", "box jump-overs"),
    "wall_ball": ("wall ball", "wall-ball", "wall ball shot", "wall-ball shot"),
    "toes_to_bar": ("toes-to-bar", "toes to bar"),
    "muscle_up": ("muscle-up", "muscle up", "muscleups"),
    "sit_up": ("sit-up", "sit up", "situps"),
    "handstand_push_up": ("handstand push-up", "handstand push-ups", "handstand push up", "handstand push ups", "hspu"),
    "walking_lunge": ("walking lunge", "walking lunges"),
    "power_clean": ("power clean", "power cleans"),
    "hang_power_clean": ("hang power clean", "hang power cleans"),
    "power_snatch": ("power snatch", "power snatches"),
    "hang_power_snatch": ("hang power snatch", "hang power snatches"),
    "overhead_squat": ("overhead squat", "overhead squats"),
    "front_squat": ("front squat", "front squats"),
    "back_squat": ("back squat", "back squats"),
    "sumo_deadlift_high_pull": ("sumo deadlift high pull", "sdlhp"),
    "clean": ("clean", "cleans"),
    "push_press": ("push press", "push presses"),
    "push_jerk": ("push jerk", "push jerks"),
    "split_jerk": ("split jerk", "split jerks"),
    "squat": ("squat", "squats"),
}

RX_FALLBACK_RULES = {
    "wall_ball": {
        "female": {"load_value_si": 6.35, "load_unit_si": "kg", "distance_value_si": 2.74, "distance_unit_si": "m"},
        "male": {"load_value_si": 9.07, "load_unit_si": "kg", "distance_value_si": 3.05, "distance_unit_si": "m"},
    },
    "box_jump": {
        "female": {"distance_value_si": 0.51, "distance_unit_si": "m"},
        "male": {"distance_value_si": 0.61, "distance_unit_si": "m"},
    },
    "box_jump_over": {
        "female": {"distance_value_si": 0.51, "distance_unit_si": "m"},
        "male": {"distance_value_si": 0.61, "distance_unit_si": "m"},
    },
}
SEX_VARIANT_PATTERN = re.compile(r"(?P<male>\d+(?:\.\d+)?)[/](?P<female>\d+(?:\.\d+)?)\s*(?P<unit>lb|lbs|kg|kgs|in|inch|ft)", re.IGNORECASE)
ROUND_PATTERN = re.compile(r"\b(?P<rounds>\d+)\s*rounds?\b", re.IGNORECASE)
EVERY_MIN_PATTERN = re.compile(r"every\s+(?P<minutes>\d+(?:\.\d+)?)\s+minutes?\s+for\s+(?P<sets>\d+)\s+sets?", re.IGNORECASE)

FORMAT_PATTERNS = {
    "amrap": re.compile(r"\bamrap\b", re.IGNORECASE),
    "for_time": re.compile(r"\bfor time\b", re.IGNORECASE),
    "emom": re.compile(r"\bemom\b", re.IGNORECASE),
    "tabata": re.compile(r"\btabata\b", re.IGNORECASE),
}
COMMENT_BLOCK_RE = re.compile(r"\b(reply|leave a comment|verify email|yesterday i did|i modified)\b", re.IGNORECASE)
PROMO_CTA_RE = re.compile(
    r"\b(learn the movement|check (?:out )?the open leaderboard|check the leaderboard|"
    r"watch the .*?(?:replay|recap)|read more|register for the open|log your score)\b",
    re.IGNORECASE,
)
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
LOAD_PATTERN = re.compile(r"\b(?P<value>\d+(?:\.\d+)?)\s*(?:-|–|—)?\s*(?P<unit>kg|kgs|lb|lbs|pood|poods)\b", re.IGNORECASE)
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
PRESCRIPTION_STOP_MARKERS = (
    "stimulus and strategy", "scaling", "intermediate option", "beginner option", "resources",
    "featured article", "learn more", "watch", "featured", "register", "leaderboard",
)
SPECIFICITY_SUPERSEDES = {
    "box_jump": {"box_jump_over"},
    "clean": {"power_clean", "hang_power_clean"},
    "power_clean": {"hang_power_clean"},
}


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
                meta = movement_index().get(movement_norm, {})
                found.append(
                    {
                        "movement_raw": alias,
                        "movement_norm": movement_norm,
                        "movement_id": movement_norm,
                        "movement_name": meta.get("name", movement_norm.replace("_", " ").title()),
                        "family": meta.get("family"),
                        "patterns": meta.get("patterns", []),
                        "implement": meta.get("implement"),
                        "skill_level": meta.get("skill_level"),
                    }
                )
                break
    return found


def _nearest_reps_before_alias(line: str, alias: str) -> int | None:
    idx = line.lower().find(alias.lower())
    if idx < 0:
        return None
    prefix = line[:idx]
    nums = re.findall(r"\b(\d{1,3})\b", prefix)
    return int(nums[-1]) if nums else None


def parse_structure_metadata(text: str) -> dict:
    metadata = {
        "rounds": None,
        "sets": None,
        "interval_minutes": None,
        "time_cap_minutes": extract_time_cap_minutes(text),
    }
    rounds_match = ROUND_PATTERN.search(text)
    if rounds_match:
        metadata["rounds"] = int(rounds_match.group("rounds"))
    every_match = EVERY_MIN_PATTERN.search(text)
    if every_match:
        metadata["interval_minutes"] = float(every_match.group("minutes"))
        metadata["sets"] = int(every_match.group("sets"))
    return metadata


def _match_movements_with_spans(segment: str) -> list[dict]:
    candidates: list[dict] = []
    for movement_id, aliases in MOVEMENT_ALIASES.items():
        for alias in aliases:
            for match in re.finditer(rf"\b{re.escape(alias)}\b", segment, re.IGNORECASE):
                candidates.append(
                    {
                        "movement_id": movement_id,
                        "alias": alias,
                        "start": match.start(),
                        "end": match.end(),
                        "length": len(alias),
                    }
                )

    # Specificity rule: longer phrase wins; overlapping generic matches are dropped.
    candidates.sort(key=lambda c: (c["length"], -(c["end"] - c["start"])), reverse=True)
    selected: list[dict] = []
    for candidate in candidates:
        overlaps = any(not (candidate["end"] <= s["start"] or candidate["start"] >= s["end"]) for s in selected)
        if overlaps:
            continue
        selected.append(candidate)

    selected.sort(key=lambda c: c["start"])
    return selected


def infer_rx_fallback(item: dict) -> dict:
    item = dict(item)
    explicit_variant = bool(item.get("female_variant") or item.get("male_variant"))
    if item.get("load_value") is not None or item.get("distance_value") is not None or explicit_variant:
        item["rx_standard_applied"] = False
        return item

    rule = RX_FALLBACK_RULES.get(item.get("movement_id"))
    if not rule:
        item["rx_standard_applied"] = False
        return item

    item["rx_standard_applied"] = True
    item["inferred_standard_source"] = "crossfit_default_2026"
    for sex, payload in rule.items():
        item[f"inferred_{sex}"] = payload
    return item


def extract_prescription_span(text: str) -> str:
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    kept: list[str] = []
    for line in lines:
        low = line.lower()
        if any(marker in low for marker in PRESCRIPTION_STOP_MARKERS):
            break
        kept.append(line)
    return "\n".join(kept)


def _apply_specificity_cleanup(items: list[dict]) -> list[dict]:
    ids = {item.get("movement_id") for item in items}
    filtered: list[dict] = []
    for item in items:
        movement_id = item.get("movement_id")
        superseded_by = SPECIFICITY_SUPERSEDES.get(movement_id, set())
        if ids.intersection(superseded_by):
            continue
        filtered.append(item)
    return filtered


def _attach_variant(items: list[dict], line: str, sex: str) -> None:
    load_entry = next((m for m in extract_measurements(line) if m.get("kind") == "load"), None)
    distance_entry = next((m for m in extract_measurements(line) if m.get("kind") == "distance"), None)
    variant_payload = {
        "load_value": load_entry.get("value_source") if load_entry else None,
        "load_unit": load_entry.get("unit_source") if load_entry else None,
        "load_value_si": load_entry.get("value_si") if load_entry else None,
        "load_unit_si": load_entry.get("unit_si") if load_entry else None,
        "distance_value": distance_entry.get("value_source") if distance_entry else None,
        "distance_unit": distance_entry.get("unit_source") if distance_entry else None,
        "distance_value_si": distance_entry.get("value_si") if distance_entry else None,
        "distance_unit_si": distance_entry.get("unit_si") if distance_entry else None,
    }
    for item in items:
        implement = item.get("implement")
        if implement == "barbell" and variant_payload["load_value"] is not None:
            item[f"{sex}_variant"] = variant_payload
        if implement == "box" and variant_payload["distance_value"] is not None:
            item[f"{sex}_variant"] = variant_payload


def extract_ordered_movements(text: str) -> list[dict]:
    items: list[dict] = []
    order_index = 1
    span_text = extract_prescription_span(text)
    structure = parse_structure_metadata(span_text)
    for line in [ln.strip() for ln in span_text.splitlines() if ln.strip()]:
        if COMMENT_BLOCK_RE.search(line):
            continue
        if line.lower() in {"workout of the day", "rest day"}:
            continue
        low = line.lower()
        if low.startswith("♀") or low.startswith("women") or low.startswith("female"):
            _attach_variant(items, line, "female")
            continue
        if low.startswith("♂") or low.startswith("men") or low.startswith("male"):
            _attach_variant(items, line, "male")
            continue
        line_measurements = extract_measurements(line)
        load_entry = next((m for m in line_measurements if m.get("kind") == "load"), None)
        distance_entry = next((m for m in line_measurements if m.get("kind") == "distance"), None)
        calorie_match = re.search(r"\b(\d+)\s*cals?\b", line, re.IGNORECASE)
        duration_match = re.search(r"\b(\d+)\s*(?:seconds?|secs?|minutes?|mins?)\b", line, re.IGNORECASE)
        sex_variant = "neutral"
        sex_matches = SEX_VARIANT_PATTERN.findall(line)
        if sex_matches:
            sex_variant = "male_female"

        segments = [s.strip() for s in re.split(r",|\band\b|/", line) if s.strip()]
        for segment in segments:
            matches = _match_movements_with_spans(segment)
            for matched in matches:
                movement = next((m for m in detect_movements(matched["alias"]) if m.get("movement_id") == matched["movement_id"]), None)
                if not movement:
                    movement = {
                        "movement_id": matched["movement_id"],
                        "movement_name": movement_index().get(matched["movement_id"], {}).get("name", matched["movement_id"]),
                        "family": movement_index().get(matched["movement_id"], {}).get("family"),
                        "patterns": movement_index().get(matched["movement_id"], {}).get("patterns", []),
                        "implement": movement_index().get(matched["movement_id"], {}).get("implement"),
                        "skill_level": movement_index().get(matched["movement_id"], {}).get("skill_level"),
                        "movement_raw": matched["alias"],
                        "movement_norm": matched["movement_id"],
                    }
                reps_value = _nearest_reps_before_alias(segment, matched["alias"])
                entry = {
                    "kind": "movement",
                    "order_index": order_index,
                "movement_id": movement.get("movement_id"),
                "movement_name": movement.get("movement_name"),
                "family": movement.get("family"),
                "patterns": movement.get("patterns", []),
                "implement": movement.get("implement"),
                "skill_level": movement.get("skill_level"),
                "movement_raw": movement.get("movement_raw"),
                "movement_norm": movement.get("movement_norm"),
                "reps": reps_value,
                "calories": int(calorie_match.group(1)) if calorie_match else None,
                "duration_seconds": None,
                "distance_value": distance_entry.get("value_source") if distance_entry else None,
                "distance_unit": distance_entry.get("unit_source") if distance_entry else None,
                "distance_value_si": distance_entry.get("value_si") if distance_entry else None,
                "distance_unit_si": distance_entry.get("unit_si") if distance_entry else None,
                "load_value": load_entry.get("value_source") if load_entry else None,
                "load_unit": load_entry.get("unit_source") if load_entry else None,
                "load_value_si": load_entry.get("value_si") if load_entry else None,
                "load_unit_si": load_entry.get("unit_si") if load_entry else None,
                "sex_variant": sex_variant,
                    "notes": segment,
                    "rounds": structure.get("rounds"),
                    "sets": structure.get("sets"),
                    "interval_minutes": structure.get("interval_minutes"),
                }
                if duration_match:
                    val = int(duration_match.group(1))
                    if "min" in duration_match.group(0).lower():
                        entry["duration_seconds"] = val * 60
                    else:
                        entry["duration_seconds"] = val
                items.append(entry)
                order_index += 1

    compact = _apply_specificity_cleanup(items)
    for item in compact:
        infered = infer_rx_fallback(item)
        item.clear()
        item.update(infered)
    return compact


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


def extract_time_cap_minutes(text: str) -> float | None:
    match = re.search(r"\btime\s*cap\s*(?:of|:)??\s*(\d+(?:\.\d+)?)\s*(min|minutes?)\b", text, re.IGNORECASE)
    if not match:
        return None
    return float(match.group(1))


def extract_score_hints(text: str) -> str | None:
    hints = []
    for line in text.splitlines():
        low = line.lower()
        if "post" in low and "time" in low:
            hints.append(line.strip())
        if "score" in low and ("round" in low or "reps" in low or "time" in low):
            hints.append(line.strip())
    return " | ".join(dict.fromkeys(hints)) if hints else None


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

    if PROMO_CTA_RE.search(text):
        score -= 6
        reasons.append("promo cta markers")

    return score, reasons


def select_main_wod_block(raw_text: str) -> tuple[str | None, bool, int, list[str]]:
    blocks = split_into_blocks(raw_text)
    if not blocks:
        return None, True, -999, ["no blocks"]

    candidates: list[dict] = []
    for block in blocks:
        score, reasons = score_wod_block(block)
        has_structure = bool(STRUCTURE_RE.search(block) or WOD_STRUCTURE_RE.search(block) or is_strength_line(block) or STRENGTH_SCHEME_RE.search(block))
        has_movement = bool(detect_movements(block))
        has_measurable = has_measurable_quantity(block)
        promo_like = bool(PROMO_CTA_RE.search(block))
        candidates.append(
            {
                "block": block,
                "score": score,
                "reasons": reasons,
                "has_structure": has_structure,
                "has_movement": has_movement,
                "has_measurable": has_measurable,
                "promo_like": promo_like,
            }
        )

    strong_candidates = [
        c for c in candidates if c["has_structure"] and c["has_movement"] and c["has_measurable"] and c["score"] >= 6
    ]
    ranked_pool = strong_candidates if strong_candidates else candidates
    winner = max(ranked_pool, key=lambda c: c["score"], default=None)
    best_block = winner["block"] if winner else None
    best_score = int(winner["score"]) if winner else -999
    best_reasons = list(winner["reasons"]) if winner else []

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


def finalize_record_status(
    *,
    page_type: str,
    parse_text: str,
    workout_format: str | None,
    movements: list[dict],
    measurements: list[dict],
    block_score: int | None,
    richer_wod_exists: bool = False,
) -> tuple[str, int, int, int]:
    low = parse_text.lower()
    has_movement = bool(movements)
    has_measurement = bool(measurements)
    movement_hits = len(movements)
    has_structure = bool(STRUCTURE_RE.search(parse_text) or WOD_STRUCTURE_RE.search(parse_text) or is_strength_line(parse_text) or STRENGTH_SCHEME_RE.search(parse_text))
    score_ok = (block_score or -999) >= 6
    promo_like = bool(PROMO_CTA_RE.search(parse_text))
    teaser_like = (len(parse_text.strip()) < 220 and "today, we have" in low and not has_structure and not has_measurement)

    is_rest = workout_format == "rest_day" or ("rest day" in low and not has_measurement and not has_movement)
    if is_rest:
        return "valid_rest_day", 1, 0, 0

    if promo_like and not richer_wod_exists and not has_structure and not has_measurement:
        return "editorial_ignored", 0, 0, 1

    strong_format = workout_format in {"for_time", "amrap", "tabata", "emom", "strength", "strength_skill", "mixed"}
    strong_wod = strong_format and has_structure and has_movement and has_measurement and score_ok

    strong_strength_skill = (
        workout_format == "strength_skill"
        and has_structure
        and movement_hits >= 1
        and (has_measurement or (block_score or -999) >= 9)
        and not teaser_like
    )
    if strong_strength_skill:
        return "valid_wod", 0, 0, 0

    if strong_wod:
        return "valid_wod", 0, 0, 0

    if page_type == "editorial_only" and not strong_wod:
        return "editorial_ignored", 0, 0, 1

    if page_type == "rest_day":
        return "valid_rest_day", 1, 0, 0

    return "needs_review", 0, 0, 0


def parse_one(row) -> dict:
    raw_text = row["raw_text"] or ""
    initial_status, _, is_missing, _, wod_text = classify_record(row["page_type"], raw_text)
    record_status = initial_status
    is_rest_day = 0
    is_editorial_only = 0

    parse_text = raw_text
    block_score = None
    block_reasons: list[str] = []
    richer_wod_exists = False
    if row["page_type"] != "not_found":
        wod_block, ambiguous_wod, block_score, block_reasons = select_main_wod_block(raw_text)
        if wod_block:
            wod_text = wod_block
            parse_text = wod_block
            for candidate in split_into_blocks(raw_text):
                if candidate.strip() == wod_block.strip():
                    continue
                c_score, _ = score_wod_block(candidate)
                c_structure = bool(STRUCTURE_RE.search(candidate) or WOD_STRUCTURE_RE.search(candidate) or is_strength_line(candidate) or STRENGTH_SCHEME_RE.search(candidate))
                c_movement = bool(detect_movements(candidate))
                c_measure = has_measurable_quantity(candidate)
                if c_score >= 6 and c_structure and c_movement and c_measure:
                    richer_wod_exists = True
                    break
        if ambiguous_wod and record_status == "valid_wod":
            record_status = "needs_review"

    movements = detect_movements(parse_text)
    ordered_movements = extract_ordered_movements(parse_text)
    measurements = extract_measurements(parse_text)
    workout_format = detect_workout_format(parse_text)
    rpe_source = extract_rpe_source(parse_text)

    if row["page_type"] != "not_found":
        record_status, is_rest_day, _, is_editorial_only = finalize_record_status(
            page_type=row["page_type"],
            parse_text=parse_text,
            workout_format=workout_format,
            movements=movements,
            measurements=measurements,
            block_score=block_score,
            richer_wod_exists=richer_wod_exists,
        )

    if record_status == "valid_rest_day":
        ordered_movements = []

    tags = []
    if is_rest_day:
        tags.append("rest_day")
    if is_editorial_only:
        tags.append("editorial_only")
    if movements:
        tags.append("has_movements")
    if ordered_movements:
        tags.append("has_ordered_movements")
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
        "compare_to_text": extract_compare_to(parse_text),
        "score_text": extract_score_hints(parse_text),
        "rpe_source": rpe_source,
        "workout_format": workout_format,
        "movement_list_json": json.dumps(ordered_movements + measurements, ensure_ascii=False),
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
