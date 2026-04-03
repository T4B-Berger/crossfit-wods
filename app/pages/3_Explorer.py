from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

st.title("Explorer")
path = Path("data/curated/crossfit_wods.parquet")
if not path.exists():
    st.warning("Dataset non disponible")
    st.stop()

df = pd.read_parquet(path)
st.bar_chart(df["record_status"].value_counts())
if "energy_system_primary" in df.columns:
    st.bar_chart(df["energy_system_primary"].fillna("indéterminée").value_counts())
