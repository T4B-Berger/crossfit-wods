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

## Détection WOD (évolutions récentes)
- **Strength WOD detection** : meilleure reconnaissance des WODs de force historiques (ex. formulations type `find your best`, schémas `5,3,1 reps`, lifts classiques).
- **Editorial block stopping** : lorsqu'un bloc WOD valide est détecté, l'extraction s'arrête avant les sections éditoriales/ressources (articles, liens externes, etc.).
- **Monostructural WOD support** : prise en charge des formats simples mono-mouvement (ex. rounds + run avec distance mesurable).
- **Règle conservatrice** : un WOD n'est validé que si on retrouve **structure d'entraînement + mouvement + quantité mesurable** (reps, distance ou temps).
