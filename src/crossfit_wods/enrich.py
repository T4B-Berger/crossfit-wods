from __future__ import annotations

import argparse
import json
import re

from .db import get_conn
from .taxonomy import TIME_DOMAIN_LABELS
from .units import to_kg, to_meters

RPE_PATTERN = re.compile(r"\brpe\s*(\d{1,2}(?:\.\d)?)", re.IGNORECASE)


def infer_energy_system(wod_text: str | None, movements: list[dict]) -> tuple[str, str, str, str, int | None, str]:
    text = (wod_text or "").lower()
    if not text:
        return "indéterminée", "indéterminée", "heuristic_v1", "low", None, "unknown"
    if "1 rm" in text or "1rm" in text or "max" in text:
        return "anaérobie alactique", "indéterminée", "heuristic_v1", "medium", 240, "under_5"
    if "amrap 20" in text or "20 min" in text:
        return "aérobie", "anaérobie lactique", "heuristic_v1", "medium", 1200, "10_to_20"
    if len(movements) >= 3:
        return "mixte", "anaérobie lactique", "heuristic_v1", "low", 720, "10_to_20"
    return "indéterminée", "indéterminée", "heuristic_v1", "low", None, "unknown"


def infer_rpe(rpe_source: str | None, wod_text: str | None, movement_count: int) -> tuple[float | None, str, str]:
    if rpe_source:
        match = RPE_PATTERN.search(rpe_source)
        if match:
            return float(match.group(1)), "source_text", "high"
    text = (wod_text or "").lower()
    if "for time" in text or "amrap" in text:
        return 7.5 if movement_count < 4 else 8.0, "heuristic_v1", "low"
    if "1 rm" in text or "1rm" in text:
        return 8.5, "heuristic_v1", "medium"
    return None, "heuristic_v1", "low"


def update_movement_si(conn, wod_date: str) -> None:
    rows = conn.execute("SELECT id, load_value_source, load_unit_source, distance_value_source, distance_unit_source FROM movements WHERE wod_date = ?", (wod_date,)).fetchall()
    for row in rows:
        load_si = None
        load_unit_si = None
        if row["load_value_source"] is not None and row["load_unit_source"]:
            try:
                load_si = to_kg(float(row["load_value_source"]), row["load_unit_source"])
                load_unit_si = "kg"
            except ValueError:
                load_si = None
                load_unit_si = None

        distance_si = None
        distance_unit_si = None
        if row["distance_value_source"] is not None and row["distance_unit_source"]:
            try:
                distance_si = to_meters(float(row["distance_value_source"]), row["distance_unit_source"])
                distance_unit_si = "m"
            except ValueError:
                distance_si = None
                distance_unit_si = None

        conn.execute(
            """
            UPDATE movements
            SET load_value_si = ?, load_unit_si = ?, distance_value_si = ?, distance_unit_si = ?
            WHERE id = ?
            """,
            (load_si, load_unit_si, distance_si, distance_unit_si, row["id"]),
        )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    args = parser.parse_args()

    with get_conn(args.db_path) as conn:
        rows = conn.execute("SELECT wod_date, wod_text, movement_list_json, record_status, rpe_source FROM daily_wods").fetchall()
        for row in rows:
            update_movement_si(conn, row["wod_date"])

            if row["record_status"] != "valid_wod":
                conn.execute(
                    """
                    UPDATE daily_wods
                    SET enrichment_version = 'v2',
                        rpe_inference_method = NULL,
                        rpe_confidence = NULL
                    WHERE wod_date = ?
                    """,
                    (row["wod_date"],),
                )
                conn.commit()
                continue

            movements = json.loads(row["movement_list_json"] or "[]")
            primary, secondary, method, conf, duration_sec, td_code = infer_energy_system(row["wod_text"], movements)
            rpe_value, rpe_method, rpe_conf = infer_rpe(row["rpe_source"], row["wod_text"], len(movements))
            rpe_method = rpe_method or 'unknown'
            rpe_conf = rpe_conf or 'low'
            conn.execute(
                """
                UPDATE daily_wods
                SET energy_system_primary = ?,
                    energy_system_secondary = ?,
                    energy_system_inference_method = ?,
                    energy_system_confidence = ?,
                    estimated_duration_sec = ?,
                    time_domain_code = ?,
                    time_domain_label_fr = ?,
                    rpe_inferred = ?,
                    rpe_inference_method = ?,
                    rpe_confidence = ?,
                    enrichment_version = 'v2',
                    last_updated_at = CURRENT_TIMESTAMP
                WHERE wod_date = ?
                """,
                (
                    primary,
                    secondary,
                    method,
                    conf,
                    duration_sec,
                    td_code,
                    TIME_DOMAIN_LABELS[td_code],
                    rpe_value,
                    rpe_method,
                    rpe_conf,
                    row["wod_date"],
                ),
            )
            conn.commit()
            print(f"enriched {row['wod_date']}")


if __name__ == "__main__":
    main()
