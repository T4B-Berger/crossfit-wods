from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path

ALLOWED_FETCH_STATUS = ("pending", "success", "not_found", "timeout", "http_error", "network_error")
ALLOWED_PAGE_TYPE = ("wod", "rest_day", "editorial_only", "not_found", "unknown")
ALLOWED_RECORD_STATUS = ("valid_wod", "valid_rest_day", "missing_page", "editorial_ignored", "needs_review")

SCHEMA = """
CREATE TABLE IF NOT EXISTS daily_pages (
    wod_date TEXT PRIMARY KEY,
    expected_url TEXT NOT NULL,
    resolved_url TEXT,
    fetch_status TEXT NOT NULL DEFAULT 'pending' CHECK (fetch_status IN ('pending', 'success', 'not_found', 'timeout', 'http_error', 'network_error')),
    http_status INTEGER,
    content_hash TEXT,
    page_type TEXT NOT NULL DEFAULT 'unknown' CHECK (page_type IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')),
    scraped_at TEXT,
    parse_status TEXT NOT NULL DEFAULT 'pending',
    parse_error TEXT,
    raw_text TEXT,
    html_path TEXT
);

CREATE TABLE IF NOT EXISTS daily_wods (
    wod_date TEXT PRIMARY KEY,
    source_url TEXT,
    record_status TEXT NOT NULL CHECK (record_status IN ('valid_wod', 'valid_rest_day', 'missing_page', 'editorial_ignored', 'needs_review')),
    page_type TEXT NOT NULL CHECK (page_type IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')),
    is_rest_day INTEGER NOT NULL DEFAULT 0,
    is_missing INTEGER NOT NULL DEFAULT 0,
    is_editorial_only INTEGER NOT NULL DEFAULT 0,
    title TEXT,
    wod_text TEXT,
    notes_text TEXT,
    score_text TEXT,
    compare_to_text TEXT,
    rpe_source TEXT,
    rpe_inference_method TEXT,
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

STATUS_VALIDATION_TRIGGERS = """
CREATE TRIGGER IF NOT EXISTS trg_daily_pages_fetch_status_insert
BEFORE INSERT ON daily_pages
WHEN NEW.fetch_status NOT IN ('pending', 'success', 'not_found', 'timeout', 'http_error', 'network_error')
BEGIN
    SELECT RAISE(FAIL, 'invalid fetch_status');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_pages_fetch_status_update
BEFORE UPDATE OF fetch_status ON daily_pages
WHEN NEW.fetch_status NOT IN ('pending', 'success', 'not_found', 'timeout', 'http_error', 'network_error')
BEGIN
    SELECT RAISE(FAIL, 'invalid fetch_status');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_pages_page_type_insert
BEFORE INSERT ON daily_pages
WHEN NEW.page_type NOT IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')
BEGIN
    SELECT RAISE(FAIL, 'invalid page_type');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_pages_page_type_update
BEFORE UPDATE OF page_type ON daily_pages
WHEN NEW.page_type NOT IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')
BEGIN
    SELECT RAISE(FAIL, 'invalid page_type');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_wods_record_status_insert
BEFORE INSERT ON daily_wods
WHEN NEW.record_status NOT IN ('valid_wod', 'valid_rest_day', 'missing_page', 'editorial_ignored', 'needs_review')
BEGIN
    SELECT RAISE(FAIL, 'invalid record_status');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_wods_record_status_update
BEFORE UPDATE OF record_status ON daily_wods
WHEN NEW.record_status NOT IN ('valid_wod', 'valid_rest_day', 'missing_page', 'editorial_ignored', 'needs_review')
BEGIN
    SELECT RAISE(FAIL, 'invalid record_status');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_wods_page_type_insert
BEFORE INSERT ON daily_wods
WHEN NEW.page_type NOT IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')
BEGIN
    SELECT RAISE(FAIL, 'invalid page_type');
END;

CREATE TRIGGER IF NOT EXISTS trg_daily_wods_page_type_update
BEFORE UPDATE OF page_type ON daily_wods
WHEN NEW.page_type NOT IN ('wod', 'rest_day', 'editorial_only', 'not_found', 'unknown')
BEGIN
    SELECT RAISE(FAIL, 'invalid page_type');
END;
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_columns(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(daily_wods)")}
    if "rpe_inference_method" not in columns:
        conn.execute("ALTER TABLE daily_wods ADD COLUMN rpe_inference_method TEXT")


def init_db(db_path: str | Path) -> None:
    with connect(db_path) as conn:
        conn.executescript(SCHEMA)
        ensure_columns(conn)
        conn.executescript(STATUS_VALIDATION_TRIGGERS)
        conn.commit()


@contextmanager
def get_conn(db_path: str | Path):
    conn = connect(db_path)
    try:
        yield conn
    finally:
        conn.close()
