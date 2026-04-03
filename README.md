# CrossFit WODs

Socle frugal pour collecter, parser, enrichir et explorer l'historique des WODs CrossFit.

## Stack
- Python 3.11+
- SQLite
- pandas
- requests + BeautifulSoup
- Streamlit

## Structure
- `src/crossfit_wods/collect.py` : initialisation DB + scraping incrémental
- `src/crossfit_wods/parse.py` : classification et extraction des WODs
- `src/crossfit_wods/enrich.py` : enrichissement métrique et tags métiers
- `src/crossfit_wods/export.py` : exports Parquet/CSV
- `app/` : interface Streamlit

## Installation
```bash
pip install -r requirements.txt
pip install -e .
```

## Usage
```bash
python -m crossfit_wods.collect init-db --db-path data/curated/crossfit_wods.sqlite --start-date 2001-02-10
python -m crossfit_wods.collect scrape --db-path data/curated/crossfit_wods.sqlite --limit 100
python -m crossfit_wods.parse --db-path data/curated/crossfit_wods.sqlite --limit 200
python -m crossfit_wods.enrich --db-path data/curated/crossfit_wods.sqlite
python -m crossfit_wods.export --db-path data/curated/crossfit_wods.sqlite --out-dir data/curated
streamlit run app/Home.py
```

## Notes
- Le scrape écrit au fil de l'eau avec commit par date.
- Le parseur est volontairement conservateur.
- Les unités impériales sont conservées, avec conversion SI en parallèle.
- Les filières énergétiques sont stockées en terminologie française.
