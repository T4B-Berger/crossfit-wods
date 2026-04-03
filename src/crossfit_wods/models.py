from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(slots=True)
class DailyPage:
    wod_date: str
    expected_url: str
    resolved_url: Optional[str]
    fetch_status: str
    http_status: Optional[int]
    content_hash: Optional[str]
    page_type: str
    scraped_at: Optional[str]
    parse_status: str
    parse_error: Optional[str]
    raw_text: Optional[str]
    html_path: Optional[str]


@dataclass(slots=True)
class DailyWod:
    wod_date: str
    source_url: Optional[str]
    record_status: str
    page_type: str
    is_rest_day: int
    is_missing: int
    is_editorial_only: int
    title: Optional[str]
    wod_text: Optional[str]
    notes_text: Optional[str]
    score_text: Optional[str]
    compare_to_text: Optional[str]
    rpe_source: Optional[str]
    rpe_inferred: Optional[float]
    rpe_confidence: Optional[str]
    energy_system_primary: Optional[str]
    energy_system_secondary: Optional[str]
    energy_system_inference_method: Optional[str]
    energy_system_confidence: Optional[str]
    time_domain_code: Optional[str]
    time_domain_label_fr: Optional[str]
    estimated_duration_sec: Optional[int]
    workout_format: Optional[str]
    movement_list_json: Optional[str]
    tags_json: Optional[str]
    parser_version: str = "v1"
    enrichment_version: Optional[str] = None
