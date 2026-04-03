from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional

import requests
from bs4 import BeautifulSoup

USER_AGENT = "Mozilla/5.0 (compatible; CrossfitWodsBot/0.1; +https://github.com/)"


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
    page_type = classify_page(text)
    return FetchResult(d.isoformat(), url, response.url, "success", response.status_code, content_hash, page_type, text, html)


def classify_page(text: str) -> str:
    low = text.lower()
    if "rest day" in low:
        return "rest_day"
    markers = ["for time", "amrap", "tabata", "rounds for time", "complete as many rounds", "then", "reps"]
    if sum(1 for m in markers if m in low) >= 2:
        return "wod"
    if len(text) < 120:
        return "unknown"
    return "editorial_only"


def persist_html(html_root: str | Path, wod_date: str, html: str) -> str:
    root = Path(html_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / f"{wod_date}.html"
    path.write_text(html, encoding="utf-8")
    return str(path)
