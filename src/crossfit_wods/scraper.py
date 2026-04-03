from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

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
    text = soup.get_text("\n", strip=True)
    content_hash = hashlib.sha256(html.encode("utf-8")).hexdigest()
    page_type = classify_page(soup, text)
    return FetchResult(d.isoformat(), url, response.url, "success", response.status_code, content_hash, page_type, text, html)


def classify_page(soup: BeautifulSoup, text: str) -> str:
    low = text.lower()
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
