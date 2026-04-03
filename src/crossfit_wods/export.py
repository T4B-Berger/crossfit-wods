from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .db import get_conn


def build_quality_metrics(wods: pd.DataFrame, pages: pd.DataFrame, movements: pd.DataFrame) -> pd.DataFrame:
    record_status_counts = wods["record_status"].fillna("unknown").value_counts().to_dict() if "record_status" in wods.columns else {}
    fetch_status_counts = pages["fetch_status"].fillna("unknown").value_counts().to_dict() if "fetch_status" in pages.columns else {}

    metrics = {
        "total_days": int(len(pages)),
        "total_wod_rows": int(len(wods)),
        "needs_review": int(record_status_counts.get("needs_review", 0)),
        "valid_wod": int(record_status_counts.get("valid_wod", 0)),
        "missing_page": int(record_status_counts.get("missing_page", 0)),
        "fetch_success": int(fetch_status_counts.get("success", 0)),
        "fetch_not_found": int(fetch_status_counts.get("not_found", 0)),
        "total_movements_rows": int(len(movements)),
    }

    if not pages.empty and "wod_date" in pages.columns:
        metrics["coverage_start"] = str(pages["wod_date"].min())
        metrics["coverage_end"] = str(pages["wod_date"].max())
    else:
        metrics["coverage_start"] = None
        metrics["coverage_end"] = None

    return pd.DataFrame([{"metric": key, "value": value} for key, value in metrics.items()])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-path", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    with get_conn(args.db_path) as conn:
        wods = pd.read_sql_query("SELECT * FROM daily_wods ORDER BY wod_date", conn)
        pages = pd.read_sql_query("SELECT * FROM daily_pages ORDER BY wod_date", conn)
        movements = pd.read_sql_query("SELECT * FROM movements ORDER BY wod_date, id", conn)

    quality = build_quality_metrics(wods, pages, movements)

    wods.to_csv(out_dir / "crossfit_wods.csv", index=False)
    pages.to_csv(out_dir / "daily_pages.csv", index=False)
    movements.to_csv(out_dir / "movements.csv", index=False)
    quality.to_csv(out_dir / "quality_metrics.csv", index=False)

    wods.to_parquet(out_dir / "crossfit_wods.parquet", index=False)
    pages.to_parquet(out_dir / "daily_pages.parquet", index=False)
    movements.to_parquet(out_dir / "movements.parquet", index=False)
    quality.to_parquet(out_dir / "quality_metrics.parquet", index=False)
    print(f"exported to {out_dir}")


if __name__ == "__main__":
    main()
