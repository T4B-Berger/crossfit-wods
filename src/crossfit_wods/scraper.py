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
WOD_FORMAT_MARKERS = ("for time", "amrap", "emom", "tabata", "rounds for time")
EDITORIAL_MARKERS = ("crossfit games", "nutrition", "podcast", "article", "opinion")
WOD_STRUCTURE_RE = re.compile(r"(^|\s)(\d+(?:\s*[-x]\s*\d+)+|\d+\s*rounds?)", re.IGNORECASE)


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
    structure_hits = len(soup.select("article ul li, article ol li, article h2, article h3"))
    wod_line_hits = sum(1 for line in text.splitlines() if WOD_STRUCTURE_RE.search(line))
    editorial_hits = sum(1 for marker in EDITORIAL_MARKERS if marker in low)

    if rest_hits and format_hits == 0:
        return "rest_day"

    strong_wod_signal = (format_hits >= 2 or wod_line_hits >= 2) or (format_hits >= 1 and wod_line_hits >= 1)
    has_workout_structure = structure_hits >= 2
    if strong_wod_signal and has_workout_structure:
        return "wod"

    if len(text) >= 180 and editorial_hits >= 1 and not strong_wod_signal:
        return "editorial_only"

    return "unknown"


def persist_html(html_root: str | Path, wod_date: str, html: str) -> str:
    root = Path(html_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{wod_date}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
