from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="CrossFit WODs", layout="wide")

st.title("CrossFit WODs Explorer")
st.write("Interface légère de consultation d'un dataset figé.")

wods_path = Path("data/curated/crossfit_wods.parquet")
pages_path = Path("data/curated/daily_pages.parquet")

if wods_path.exists():
    wods = pd.read_parquet(wods_path)
    pages = pd.read_parquet(pages_path) if pages_path.exists() else pd.DataFrame()

    total_days = len(pages) if not pages.empty else len(wods)
    needs_review = int((wods["record_status"] == "needs_review").sum()) if "record_status" in wods.columns else 0
    coverage_start = pages["wod_date"].min() if (not pages.empty and "wod_date" in pages.columns) else wods["wod_date"].min()
    coverage_end = pages["wod_date"].max() if (not pages.empty and "wod_date" in pages.columns) else wods["wod_date"].max()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Nombre total de jours", int(total_days))
    m2.metric("Lignes WOD", int(len(wods)))
    m3.metric("needs_review", needs_review)
    m4.metric("Couverture", f"{coverage_start} → {coverage_end}")

    st.subheader("Répartition par record_status")
    if "record_status" in wods.columns:
        st.bar_chart(wods["record_status"].fillna("unknown").value_counts())
    else:
        st.info("Colonne record_status absente")

    st.subheader("Aperçu")
    st.dataframe(wods.head(50), use_container_width=True)
else:
    st.info("Aucun export Parquet trouvé. Lance d'abord collect -> parse -> enrich -> export.")
