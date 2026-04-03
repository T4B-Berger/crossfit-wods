from __future__ import annotations

import argparse
import json

from .db import get_conn
from .taxonomy import TIME_DOMAIN_LABELS


def infer_energy_system(wod_text: str | None, movements: list[dict]) -> tuple[str, str, str, str, int | None, str, float | None, str]:
    text = (wod_text or "").lower()
    if not text:
        return "indéterminée", "aucune", "heuristic_v1", "low", None, "unknown", None, "low"
    if "1 rm" in text or "1rm" in text or "max" in text:
        return "anaérobie alactique", "aucune", "heuristic_v1", "medium", 240, "under_5", 8.5, "medium"
    if "amrap 20" in text or "20 min" in text:
        return "aérobie", "anaérobie lactique", "heuristic_v1", "medium", 1200, "10_to_20", 7.0, "low"
    if len(movements) >= 3:
        return "anaérobie lactique", "aérobie", "heuristic_v1", "low", 720, "10_to_20", 8.0, "low"
    return "indéterminée", "aucune", "heuristic_v1", "low", None, "unknown", None, "low"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    args = parser.parse_args()

    with get_conn(args.db_path) as conn:
        rows = conn.execute("SELECT wod_date, wod_text, movement_list_json, record_status FROM daily_wods").fetchall()
        for row in rows:
            if row["record_status"] != "valid_wod":
                conn.execute(
                    """
                    UPDATE daily_wods
                    SET enrichment_version = 'v1'
                    WHERE wod_date = ?
                    """,
                    (row["wod_date"],),
                )
                conn.commit()
                continue

            movements = json.loads(row["movement_list_json"] or "[]")
            primary, secondary, method, conf, duration_sec, td_code, rpe, rpe_conf = infer_energy_system(row["wod_text"], movements)
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
                    rpe_confidence = ?,
                    enrichment_version = 'v1',
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
                    rpe,
                    rpe_conf,
                    row["wod_date"],
                ),
            )
            conn.commit()
            print(f"enriched {row['wod_date']}")


if __name__ == "__main__":
    main()
