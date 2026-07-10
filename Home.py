"""aitrader — single app, two pages (Trading News + Bot Dashboard).

Main entry for Streamlit. The sidebar shows the pages in pages/.
Deploy with Main file path = Home.py.
"""
import streamlit as st

st.set_page_config(page_title="aitrader", page_icon="🤖", layout="wide")

st.title("🤖 aitrader")
st.caption("AI trading bot + live news — ek hi app me. Left sidebar se page chuno.")

col1, col2 = st.columns(2)
with col1:
    st.subheader("📈 Trading News")
    st.write("Crypto + Global + India ki latest news, free sources, sentiment tags, "
             "aur 'ideas to watch for our bot' panel.")
    st.caption("Sidebar → **Trading News**")
with col2:
    st.subheader("🤖 Bot Dashboard")
    st.write("Humara architecture ka live diagram, agent debate wala decision, "
             "aur net-of-cost backtest.")
    st.caption("Sidebar → **Bot Dashboard**")

st.markdown("---")
st.info("👈 Upar-left sidebar me **do pages** dikhenge. Phone pe sidebar ke liye "
        "upar-left **›** arrow dabao.")
st.warning("⚠️ Sirf education/info. Koi bhi bot 100% profit guarantee nahi karta.")
