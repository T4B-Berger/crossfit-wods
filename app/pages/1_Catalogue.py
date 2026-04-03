from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

st.title("Catalogue")
path = Path("data/curated/crossfit_wods.parquet")
if not path.exists():
    st.warning("Dataset non disponible")
    st.stop()

df = pd.read_parquet(path)
status = st.multiselect("Statut", sorted(df["record_status"].dropna().unique().tolist()), default=sorted(df["record_status"].dropna().unique().tolist()))
query = st.text_input("Recherche texte")
filtered = df[df["record_status"].isin(status)]
if query:
    filtered = filtered[filtered["wod_text"].fillna("").str.contains(query, case=False, regex=False) | filtered["title"].fillna("").str.contains(query, case=False, regex=False)]
st.dataframe(filtered, use_container_width=True)
