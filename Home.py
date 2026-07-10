"""aitrader — attractive landing page with easy navigation to both tools."""
import streamlit as st

st.set_page_config(page_title="aitrader", page_icon="🤖", layout="wide",
                   initial_sidebar_state="expanded")

st.markdown("""
<style>
  .hero {text-align:center; padding: 1.4rem 0 0.6rem;}
  .hero h1 {font-size: 2.6rem; margin-bottom: .2rem;
            background: linear-gradient(90deg,#16C784,#2E8BFF);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
  .hero p {color:#9BA6B2; font-size:1.05rem; margin-top:0;}
  .card {background:#161B22; border:1px solid #26303B; border-radius:18px;
         padding:1.4rem 1.5rem; height:100%;}
  .card h3 {margin:.1rem 0 .4rem; font-size:1.3rem;}
  .card p {color:#9BA6B2; font-size:.95rem; min-height:3.2rem;}
  .pill {display:inline-block; background:#0E2A1E; color:#16C784; border:1px solid #16C78455;
         border-radius:999px; padding:.15rem .7rem; font-size:.78rem; margin:.15rem .2rem 0 0;}
  .warn {background:#2A1E0E; color:#E6A817; border:1px solid #E6A81744; border-radius:12px;
         padding:.7rem 1rem; font-size:.9rem; text-align:center; margin-top:1rem;}
</style>
<div class="hero">
  <h1>🤖 aitrader</h1>
  <p>AI trading research bot + live market news — ek hi app, phone-friendly.</p>
</div>
""", unsafe_allow_html=True)

c1, c2 = st.columns(2, gap="large")
with c1:
    st.markdown("""
    <div class="card">
      <h3>📈 Trading News</h3>
      <p>Crypto + Global + India ki latest news ek feed me — free sources, sentiment tags,
         aur "ideas to watch for our bot".</p>
      <span class="pill">Live RSS</span><span class="pill">No keys</span><span class="pill">Sentiment</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/1_Trading_News.py", label="Open Trading News  →", icon="📈",
                 use_container_width=True)
with c2:
    st.markdown("""
    <div class="card">
      <h3>🤖 Bot Dashboard</h3>
      <p>Architecture ka live diagram, agent debate wala decision, net-of-cost backtest,
         aur validation gauntlet ke results.</p>
      <span class="pill">Architecture</span><span class="pill">Live decision</span><span class="pill">Backtest</span>
    </div>""", unsafe_allow_html=True)
    st.page_link("pages/2_Bot_Dashboard.py", label="Open Bot Dashboard  →", icon="🤖",
                 use_container_width=True)

st.markdown("<br>", unsafe_allow_html=True)
m1, m2, m3 = st.columns(3)
m1.metric("Edge candidates tested", "2", "funding + TSMOM")
m2.metric("Passed the gauntlet", "0", "honest R&D", delta_color="off")
m3.metric("Cost to run", "$0", "all free")

st.markdown("""
<div class="warn">⚠️ Yeh ek research/learning tool hai — koi bhi bot 100% profit guarantee
nahi karta. Abhi tak koi deployable edge nahi mila (aur wo bhi ek imaandaar result hai).</div>
""", unsafe_allow_html=True)

st.caption("👈 Sidebar se pages kholo. Phone pe: browser menu → 'Add to Home screen'.")
