from __future__ import annotations

from pathlib import Path
import pandas as pd
import streamlit as st

st.title("Block Builder")
st.write("Prototype simple. Cette page servira à composer des blocs de 4 semaines à partir du dataset enrichi.")
path = Path("data/curated/crossfit_wods.parquet")
if path.exists():
    df = pd.read_parquet(path)
    valid = df[df["record_status"] == "valid_wod"].copy()
    st.write(f"WOD valides disponibles: {len(valid)}")
