from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup
from bs4.element import Tag

USER_AGENT = "Mozilla/5.0 (compatible; CrossfitWodsBot/0.1; +https://github.com/)"

REST_MARKERS = ("rest day", "restday")
WOD_FORMAT_MARKERS = ("for time", "each for time", "amrap", "emom", "tabata", "rounds for time", "rounds")
EDITORIAL_MARKERS = ("crossfit games", "nutrition", "podcast", "article", "opinion")
WOD_STRUCTURE_RE = re.compile(r"(^|\s)(\d+(?:\s*[-x]\s*\d+)+|\d+\s*rounds?)", re.IGNORECASE)
MEASURABLE_REPS_RE = re.compile(r"\b(?:\d+(?:\s*[-x]\s*\d+)+|\d+)\s*reps?\b", re.IGNORECASE)
MEASURABLE_TIME_RE = re.compile(r"\b\d+\s*(?:sec(?:ond)?s?|min(?:ute)?s?|hours?)\b|\b\d+\s*:\s*\d+\b", re.IGNORECASE)
MEASURABLE_DISTANCE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:-|–|—)?\s*(?:m|meter|meters|metre|metres|km|mi|mile|miles|yd|yard|yards|ft|foot|feet)\b",
    re.IGNORECASE,
)
STRENGTH_FIND_BEST_RE = re.compile(r"\bfind\s+your\s+best\b", re.IGNORECASE)
STRENGTH_BEST_LIFT_RE = re.compile(
    r"\bbest\s+(?:back\s+)?(?:squat|deadlift|bench(?:-press|\s+press)?|press|clean|jerk|snatch)\b",
    re.IGNORECASE,
)
STRENGTH_REPS_RE = re.compile(
    r"\b(?:5\s*,\s*3\s*,\s*(?:and\s*)?1\s*reps?|(?:1|3|5)\s*rep(?:s)?)\b",
    re.IGNORECASE,
)
MOVEMENT_MARKERS = (
    "squat", "deadlift", "clean", "jerk", "snatch", "thruster", "pull-up", "push-up",
    "burpee", "run", "row", "double-under", "toes-to-bar", "muscle-up", "wall-ball",
)
WORKOUT_LABEL_MARKERS = ("workout of the day", "wod")
NON_CONTENT_SELECTORS = (
    "footer", "nav", "aside", "form", "script", "style", "noscript", "iframe",
    "[id*='comment']", "[class*='comment']", "[id*='reply']", "[class*='reply']",
    "[id*='widget']", "[class*='widget']", "[id*='share']", "[class*='share']",
    "[id*='social']", "[class*='social']",
)
LIKELY_CONTAINER_SELECTORS = (
    ("article", "article"),
    ("main article", "main article"),
    ("main", "main"),
)
CONTAINER_KEYWORDS = ("workout", "post", "entry", "content", "wod")
STRONG_WOD_TEXT_MARKERS = ("for time", "amrap", "tabata", "emom", "rounds for time", "21-15-9")
NEGATIVE_TEXT_MARKERS = ("reply", "comments", "previous post", "next post", "share", "follow us")
COMMENT_LIKE_MARKERS = (
    "reply", "leave a comment", "yesterday i did", "i modified", "modified ", "didn't have", "didnt have",
    "scaled", "rx+", "my score", "as prescribed", "find a gym", "subscribe",
)
FIRST_PERSON_MARKERS = (" i ", " i've ", " i'm ", " my ", " we ", " our ")
STRUCTURED_TEXT_KEYS = {
    "articlebody", "description", "body", "content", "text", "workout", "wod", "post", "entry", "blocks"
}


@dataclass(slots=True)
class FetchResult:
    wod_date: str
    expected_url: str
    resolved_url: Optional[str]
    fetch_status: str
    http_status: Optional[int]
    content_hash: Optional[str]
    page_type: str
    raw_text: Optional[str]
    html: Optional[str]


def build_expected_url(d: date) -> str:
    return f"https://www.crossfit.com/workout/{d.year:04d}/{d.month:02d}/{d.day:02d}"


def fetch_day(d: date, timeout: int = 20) -> FetchResult:
    url = build_expected_url(d)
    try:
        response = requests.get(url, timeout=timeout, headers={"User-Agent": USER_AGENT})
    except requests.Timeout:
        return FetchResult(d.isoformat(), url, None, "timeout", None, None, "unknown", None, None)
    except requests.RequestException:
        return FetchResult(d.isoformat(), url, None, "network_error", None, None, "unknown", None, None)

    if response.status_code == 404:
        return FetchResult(d.isoformat(), url, response.url, "not_found", 404, None, "not_found", None, None)
    if response.status_code >= 400:
        return FetchResult(d.isoformat(), url, response.url, "http_error", response.status_code, None, "unknown", None, None)

    html = response.text
    soup = BeautifulSoup(html, "lxml")
    text = extract_main_text_from_html(html)
    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    page_type = classify_page(soup, text)
    return FetchResult(d.isoformat(), url, response.url, "success", response.status_code, content_hash, page_type, text, html)


def _prune_non_content_zones(soup: BeautifulSoup) -> None:
    for selector in NON_CONTENT_SELECTORS:
        for node in soup.select(selector):
            node.decompose()


def _comment_like_reasons(text: str) -> list[str]:
    low = f" {text.lower()} "
    reasons: list[str] = []
    marker_hits = sum(1 for marker in COMMENT_LIKE_MARKERS if marker in low)
    if marker_hits:
        reasons.append(f"comment markers={marker_hits}")
    first_person_hits = sum(1 for marker in FIRST_PERSON_MARKERS if marker in low)
    if first_person_hits >= 2:
        reasons.append(f"first-person markers={first_person_hits}")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if lines and len(lines) <= 4 and marker_hits >= 1 and "workout of the day" not in low:
        reasons.append("short anecdotal comment shape")
    return reasons


def is_comment_like_text(text: str) -> bool:
    return bool(_comment_like_reasons(text))


def _describe_tag(tag: Tag) -> str:
    if tag.get("id"):
        return f"{tag.name}#{tag.get('id')}"
    classes = tag.get("class") or []
    if classes:
        return f"{tag.name}.{classes[0]}"
    return tag.name


def _score_candidate(tag: Tag, text: str) -> tuple[int, list[str]]:
    low = text.lower()
    score = 0
    reasons: list[str] = []

    if "workout of the day" in low:
        score += 8
        reasons.append("contains workout of the day")

    marker_hits = sum(1 for marker in STRONG_WOD_TEXT_MARKERS if marker in low)
    if marker_hits:
        score += marker_hits * 3
        reasons.append(f"strong wod markers={marker_hits}")

    movement_hits = sum(1 for marker in MOVEMENT_MARKERS if marker in low)
    if movement_hits:
        score += min(8, movement_hits * 2)
        reasons.append(f"movement hits={movement_hits}")

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    short_lines = [line for line in lines if 4 <= len(line) <= 80]
    if len(short_lines) >= 3:
        score += min(6, len(short_lines) // 2)
        reasons.append("has structured short lines")

    negative_hits = sum(1 for marker in NEGATIVE_TEXT_MARKERS if marker in low)
    if negative_hits:
        score -= negative_hits * 4
        reasons.append(f"negative markers={negative_hits}")

    if tag.name in {"article", "main"}:
        score += 2
        reasons.append("semantic content tag")

    comment_reasons = _comment_like_reasons(text)
    if comment_reasons:
        score -= 20
        reasons.extend(comment_reasons)

    return score, reasons


def _score_text_candidate(text: str) -> tuple[int, list[str]]:
    pseudo = BeautifulSoup("<article></article>", "lxml").article
    assert pseudo is not None
    return _score_candidate(pseudo, text)


def _collect_content_candidates(soup: BeautifulSoup) -> list[tuple[str, Tag]]:
    candidates: list[tuple[str, Tag]] = []
    seen: set[int] = set()

    for selector, label in LIKELY_CONTAINER_SELECTORS:
        for tag in soup.select(selector):
            if id(tag) in seen:
                continue
            seen.add(id(tag))
            candidates.append((label, tag))

    for tag in soup.find_all(True):
        classes = " ".join(tag.get("class") or []).lower()
        tag_id = (tag.get("id") or "").lower()
        if any(keyword in classes or keyword in tag_id for keyword in CONTAINER_KEYWORDS):
            if id(tag) in seen:
                continue
            seen.add(id(tag))
            candidates.append((f"{_describe_tag(tag)}[keyword]", tag))

    return candidates


def choose_content_container(html: str) -> tuple[Tag | None, str, str, int]:
    soup = BeautifulSoup(html, "lxml")
    _prune_non_content_zones(soup)
    candidates = _collect_content_candidates(soup)
    best: tuple[Tag | None, str, str, int] = (None, "fallback:body", "no suitable candidate", -10_000)

    for label, tag in candidates:
        text = tag.get_text("\n", strip=True)
        if len(text) < 20:
            continue
        score, reasons = _score_candidate(tag, text)
        if score > best[3]:
            best = (tag, label, "; ".join(reasons) if reasons else "no strong signal", score)

    return best


def _extract_json_candidates(payload, path: str = "$") -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    if isinstance(payload, dict):
        for key, value in payload.items():
            key_low = key.lower()
            child_path = f"{path}.{key}"
            if isinstance(value, str) and key_low in STRUCTURED_TEXT_KEYS and len(value.strip()) >= 20:
                candidates.append((child_path, value.strip()))
            else:
                candidates.extend(_extract_json_candidates(value, child_path))
    elif isinstance(payload, list):
        for idx, item in enumerate(payload):
            candidates.extend(_extract_json_candidates(item, f"{path}[{idx}]"))
    elif isinstance(payload, str) and len(payload.strip()) >= 40 and any(marker in payload.lower() for marker in STRONG_WOD_TEXT_MARKERS):
        candidates.append((path, payload.strip()))
    return candidates


def _parse_json_blobs(soup: BeautifulSoup) -> list[tuple[str, object]]:
    blobs: list[tuple[str, object]] = []
    for idx, script in enumerate(soup.find_all("script")):
        raw = (script.string or script.get_text() or "").strip()
        if not raw:
            continue
        script_id = script.get("id")
        script_type = (script.get("type") or "").lower()
        label = f"script[{idx}]"
        if script_id:
            label += f"#{script_id}"

        if "application/ld+json" in script_type:
            try:
                blobs.append((label, json.loads(raw)))
            except json.JSONDecodeError:
                continue
            continue

        if script_id == "__NEXT_DATA__":
            try:
                blobs.append((label, json.loads(raw)))
            except json.JSONDecodeError:
                continue
            continue

        if "{" not in raw or "}" not in raw:
            continue

        for match in re.finditer(r"(\{[\s\S]{40,}\})", raw):
            chunk = match.group(1).strip().rstrip(";")
            try:
                blobs.append((f"{label}:blob", json.loads(chunk)))
            except json.JSONDecodeError:
                continue

    return blobs


def select_best_text_source(html: str) -> dict:
    rejected: list[dict[str, str | int]] = []
    soup = BeautifulSoup(html, "lxml")

    best_text = ""
    best_score = -10_000
    best_source = "fallback"
    best_locator = "body"
    best_rationale = "no candidate"

    # Layer A: structured JSON / hydration payloads.
    for blob_label, payload in _parse_json_blobs(soup):
        for path, text in _extract_json_candidates(payload, blob_label):
            score, reasons = _score_text_candidate(text)
            if score > best_score:
                best_text = text
                best_score = score
                best_source = "structured_json"
                best_locator = path
                best_rationale = "; ".join(reasons) if reasons else "structured candidate"
            else:
                rejected.append({"source": "structured_json", "locator": path, "score": score, "reason": "; ".join(reasons)})

    # Layer B: DOM candidate fallback.
    dom_soup = BeautifulSoup(html, "lxml")
    _prune_non_content_zones(dom_soup)
    for label, tag in _collect_content_candidates(dom_soup):
        text = tag.get_text("\n", strip=True)
        if len(text) < 20:
            continue
        score, reasons = _score_candidate(tag, text)
        if score > best_score:
            best_text = text
            best_score = score
            best_source = "dom"
            best_locator = label
            best_rationale = "; ".join(reasons) if reasons else "dom candidate"
        else:
            rejected.append({"source": "dom", "locator": label, "score": score, "reason": "; ".join(reasons)})

    if not best_text:
        fallback_soup = BeautifulSoup(html, "lxml")
        _prune_non_content_zones(fallback_soup)
        best_text = fallback_soup.get_text("\n", strip=True)
        best_score = -500
        best_source = "fallback"
        best_locator = "body"
        best_rationale = "fallback after candidate miss"

    preview = " ".join(best_text.split())[:180]
    return {
        "source_type": best_source,
        "locator": best_locator,
        "score": best_score,
        "rationale": best_rationale,
        "preview": preview,
        "text": best_text,
        "rejected": rejected[:40],
    }


def explain_main_text_choice(html: str) -> dict[str, str | int | None]:
    details = select_best_text_source(html)
    return {
        "source_type": details["source_type"],
        "selector": details["locator"],
        "rationale": details["rationale"],
        "score": details["score"],
        "container": details["locator"],
        "preview": details["preview"],
        "rejected": details["rejected"],
    }


def extract_main_text_from_html(html: str) -> str:
    return str(select_best_text_source(html)["text"])


def classify_page(soup: BeautifulSoup, text: str) -> str:
    low = text.lower()
    if is_comment_like_text(text):
        return "unknown"
    rest_hits = sum(1 for marker in REST_MARKERS if marker in low)
    format_hits = sum(1 for marker in WOD_FORMAT_MARKERS if marker in low)
    structure_hits = len(soup.select("article li, article h2, article h3, article p, main li, main h2, main h3, main p"))
    wod_line_hits = sum(1 for line in text.splitlines() if WOD_STRUCTURE_RE.search(line))
    editorial_hits = sum(1 for marker in EDITORIAL_MARKERS if marker in low)
    movement_hits = sum(1 for marker in MOVEMENT_MARKERS if marker in low)
    workout_label_hits = sum(1 for marker in WORKOUT_LABEL_MARKERS if marker in low)
    strength_find_hits = len(STRENGTH_FIND_BEST_RE.findall(low))
    strength_best_lift_hits = len(STRENGTH_BEST_LIFT_RE.findall(low))
    strength_reps_hits = len(STRENGTH_REPS_RE.findall(low))
    measurable_hits = len(MEASURABLE_REPS_RE.findall(low)) + len(MEASURABLE_TIME_RE.findall(low)) + len(MEASURABLE_DISTANCE_RE.findall(low))

    if rest_hits and format_hits == 0:
        return "rest_day"

    has_workout_pattern = format_hits >= 1 or wod_line_hits >= 1 or workout_label_hits >= 1
    strong_wod_signal = has_workout_pattern and movement_hits >= 1 and measurable_hits >= 1
    strength_wod_signal = (
        (strength_find_hits >= 1 and strength_best_lift_hits >= 1 and strength_reps_hits >= 1)
        or (strength_best_lift_hits >= 2 and strength_reps_hits >= 1)
    )
    has_workout_structure = structure_hits >= 2
    if (strong_wod_signal or strength_wod_signal) and has_workout_structure:
        return "wod"

    if len(text) >= 180 and editorial_hits >= 1 and not strong_wod_signal and not strength_wod_signal:
        return "editorial_only"

    return "unknown"


def persist_html(html_root: str | Path, wod_date: str, html: str) -> str:
    root = Path(html_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{wod_date}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
