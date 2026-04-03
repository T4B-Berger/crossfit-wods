from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

st.title("Fiche WOD")
path = Path("data/curated/crossfit_wods.parquet")
if not path.exists():
    st.warning("Dataset non disponible")
    st.stop()

df = pd.read_parquet(path)
date_value = st.selectbox("Date", df["wod_date"].astype(str).tolist())
row = df[df["wod_date"].astype(str) == date_value].iloc[0]
st.subheader(str(row.get("title") or row["wod_date"]))
st.write(row.to_dict())
