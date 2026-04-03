from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="CrossFit WODs", layout="wide")

st.title("CrossFit WODs Explorer")
st.write("Interface légère de consultation d'un dataset figé.")

parquet_path = Path("data/curated/crossfit_wods.parquet")
if parquet_path.exists():
    df = pd.read_parquet(parquet_path)
    st.metric("Nombre de lignes", len(df))
    st.dataframe(df.head(50), use_container_width=True)
else:
    st.info("Aucun export Parquet trouvé. Lance d'abord collect -> parse -> enrich -> export.")
