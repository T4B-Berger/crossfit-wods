from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_pages (
    wod_date TEXT PRIMARY KEY,
    expected_url TEXT NOT NULL,
    resolved_url TEXT,
    fetch_status TEXT NOT NULL DEFAULT 'pending',
    http_status INTEGER,
    content_hash TEXT,
    page_type TEXT NOT NULL DEFAULT 'unknown',
    scraped_at TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    parse_error TEXT,
    raw_text TEXT,
    html_path TEXT
);

CREATE TABLE IF NOT EXISTS daily_wods (
    wod_date TEXT PRIMARY KEY,
    source_url TEXT,
    record_status TEXT NOT NULL,
    page_type TEXT NOT NULL,
    is_rest_day INTEGER NOT NULL DEFAULT 0,
    is_missing INTEGER NOT NULL DEFAULT 0,
    is_editorial_only INTEGER NOT NULL DEFAULT 0,
    title TEXT,
    wod_text TEXT,
    notes_text TEXT,
    score_text TEXT,
    compare_to_text TEXT,
    rpe_source TEXT,
    rpe_inferred REAL,
    rpe_confidence TEXT,
    energy_system_primary TEXT,
    energy_system_secondary TEXT,
    energy_system_inference_method TEXT,
    energy_system_confidence TEXT,
    time_domain_code TEXT,
    time_domain_label_fr TEXT,
    estimated_duration_sec INTEGER,
    workout_format TEXT,
    movement_list_json TEXT,
    tags_json TEXT,
    parser_version TEXT NOT NULL DEFAULT 'v1',
    enrichment_version TEXT,
    last_updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wod_date TEXT NOT NULL,
    movement_raw TEXT,
    movement_norm TEXT,
    category TEXT,
    pattern TEXT,
    modality TEXT,
    reps INTEGER,
    distance_value_source REAL,
    distance_unit_source TEXT,
    distance_value_si REAL,
    distance_unit_si TEXT,
    load_value_source REAL,
    load_unit_source TEXT,
    load_value_si REAL,
    load_unit_si TEXT,
    duration_sec INTEGER,
    context_text TEXT
);
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.commit()


@contextmanager
def get_conn(db_path: str | Path):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
