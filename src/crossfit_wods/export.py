from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from .db import get_conn


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

    wods.to_csv(out_dir / "crossfit_wods.csv", index=False)
    pages.to_csv(out_dir / "daily_pages.csv", index=False)
    movements.to_csv(out_dir / "movements.csv", index=False)

    wods.to_parquet(out_dir / "crossfit_wods.parquet", index=False)
    pages.to_parquet(out_dir / "daily_pages.parquet", index=False)
    movements.to_parquet(out_dir / "movements.parquet", index=False)
    print(f"exported to {out_dir}")


if __name__ == "__main__":
    main()
