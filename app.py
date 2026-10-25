import streamlit as st

from ui.settings import render_settings_page
from ui.relative_strength import render_relative_strength_page

st.set_page_config(
    page_title="TradeLab Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("TradeLab Pro")
st.caption("NSE/BSE Cash Market · Relative Strength workspace")

page = st.sidebar.radio(
    "Navigation",
    ["Relative Strength", "Settings (Data)"],
    index=0,
)

if page == "Settings (Data)":
    render_settings_page()
else:
    render_relative_strength_page()
