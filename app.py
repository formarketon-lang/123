import streamlit as st

from ui.settings import render_settings_page
from ui.relative_strength import render_relative_strength_page
from ui.stock_search import render_stock_search_page
from ui.data_alerts import render_data_integrity_alerts
from ui.market_intelligence import render_market_intelligence_page


st.set_page_config(
    page_title="TradeLab Pro",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("TradeLab Pro")
st.caption(
    "NSE/BSE Cash Market · Relative Strength, Stock Search & Market Intelligence"
)

# Global Data Integrity Monitor
render_data_integrity_alerts()

page = st.sidebar.radio(
    "Navigation",
    [
        "Relative Strength",
        "Stock Search",
        "Settings (Data)",
        "Market Intelligence",
    ],
    index=0,
)

if page == "Settings (Data)":
    render_settings_page()

elif page == "Stock Search":
    render_stock_search_page()

elif page == "Market Intelligence":
    render_market_intelligence_page()

else:
    render_relative_strength_page()