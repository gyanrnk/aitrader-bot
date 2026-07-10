"""Bot Dashboard — a real trading-app view: markets, decision, backtest, carry, learnings."""
from __future__ import annotations

import numpy as np
import pandas as pd
import streamlit as st

from aitrader.config import Settings
from aitrader.runner import TradingBot
from aitrader.data import get_provider
from aitrader.backtest import Backtester

st.set_page_config(page_title="Bot Dashboard", page_icon="🤖", layout="wide")

st.markdown("""
<style>
  .block-container{padding-top:2.2rem;}
  div[data-testid="stMetric"]{background:#161B22;border:1px solid #26303B;
     border-radius:14px;padding:.7rem 1rem;}
  h1,h2,h3{letter-spacing:-.3px;}
</style>
""", unsafe_allow_html=True)

st.title("🤖 aitrader — AI Trading Architecture")
st.caption("Ek research trading bot. Mock mode = free, instant, no keys. yfinance = real data.")

tabs = st.tabs(["🏗️ Architecture", "📈 Markets", "🧠 Live Decision",
                "📊 Backtest", "💰 Carry (5–10% path)", "🧪 Learnings"])
tab_arch, tab_mkt, tab_dec, tab_bt, tab_carry, tab_learn = tabs

CARRY_SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


@st.cache_data(ttl=300, show_spinner=False)
def load_ohlcv(symbol: str, provider: str, n: int = 400):
    return get_provider(Settings(data_provider=provider)).ohlcv(symbol, lookback=n)


# ----------------------------------------------------------------- ARCHITECTURE
ARCH_DOT = r"""
digraph G { rankdir=TB; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11, color="#00000000"];
  edge [color="#888888", fontsize=9];
  subgraph cluster_d {label="1 · DATA (free)";style=rounded;color="#4C8BF5";
    d1[label="Market data\n(yfinance/mock)",fillcolor="#DCE9FF"];
    d2[label="Funding rate\n(Binance)",fillcolor="#DCE9FF"];
    d3[label="🔒 Leakage firewall",fillcolor="#DCE9FF"];}
  subgraph cluster_m {label="2 · FEATURES + ML";style=rounded;color="#8E5BE8";
    m1[label="Indicators",fillcolor="#EBDDFB"];m3[label="LightGBM\nP(up)",fillcolor="#EBDDFB"];}
  subgraph cluster_a {label="3 · AGENT DEBATE";style=rounded;color="#2F9E44";
    a1[label="4 Analysts",fillcolor="#D7F5DE"];a2[label="🐂 Bull vs Bear 🐻",fillcolor="#D7F5DE"];
    a5[label="Portfolio Mgr\nBuy/Sell/Hold",fillcolor="#D7F5DE"];}
  mem[label="🧠 MEMORY\ndecay+reflect",fillcolor="#FFE8CC",color="#E8890C"];
  subgraph cluster_e {label="4 · RISK + EXEC";style=rounded;color="#E03131";
    r1[label="Sizing (caps)",fillcolor="#FFE0E0"];r2[label="Broker\npaper/ccxt",fillcolor="#FFE0E0"];}
  gate[label="🚦 DISCIPLINE GATE + VALIDATION GAUNTLET\nnet-of-cost · PBO · deflated Sharpe · falsification",
       fillcolor="#343A40",fontcolor="white"];
  d1->d3;d2->d3;d3->m1->m3->a1->a2->a5->r1->r2;
  mem->a2[style=dashed,color="#E8890C"];a5->mem[style=dashed,color="#E8890C"];
  r2->gate[style=dotted];m3->gate[style=dotted]; }
"""
with tab_arch:
    st.subheader("Poora system, ek nazar me")
    st.graphviz_chart(ARCH_DOT, use_container_width=True)
    st.info("Fast loop (har bar, FREE): data → firewall → features → agent debate → risk → paper broker. "
            "LLM sirf slow-loop me. Har strategy DISCIPLINE GATE + GAUNTLET paar kare tabhi live.")

# ----------------------------------------------------------------- MARKETS
with tab_mkt:
    st.subheader("📈 Markets")
    c = st.columns([2, 1, 1])
    sym = c[0].text_input("Symbol", "BTC-USD", key="mk_sym")
    prov = c[1].selectbox("Data", ["mock", "yfinance"], index=0, key="mk_prov")
    rng = c[2].selectbox("Range (bars)", [120, 250, 400], index=1, key="mk_rng")
    try:
        df = load_ohlcv(sym, prov, rng)
        close = df["close"]
        k = st.columns(4)
        k[0].metric("Price", f"${close.iloc[-1]:,.2f}", f"{close.iloc[-1]/close.iloc[-2]-1:+.2%}")
        k[1].metric("30-bar change", f"{close.iloc[-1]/close.iloc[-min(30,len(close))]-1:+.1%}")
        k[2].metric("Ann. volatility", f"{close.pct_change().std()*np.sqrt(365):.0%}")
        k[3].metric("Bars", f"{len(close)}")
        st.area_chart(close.rename("price"), height=300, color="#16C784")
        st.caption("Volume")
        st.bar_chart(df["volume"].tail(80), height=140, color="#2E8BFF")
    except Exception as e:
        st.error(f"Data error: {e}. Try 'mock'.")

# ----------------------------------------------------------------- LIVE DECISION
with tab_dec:
    st.subheader("🧠 Live Decision — poora reasoning")
    c = st.columns([2, 1, 1])
    d_sym = c[0].text_input("Symbol", "BTC-USD", key="d_sym")
    d_prov = c[1].selectbox("Data", ["mock", "yfinance"], index=0, key="d_prov")
    d_run = c[2].button("▶️ Run decision", use_container_width=True)
    if d_run or "decided" not in st.session_state:
        st.session_state["decided"] = True
        try:
            bot = TradingBot(Settings(mode="mock", data_provider=d_prov))
            with st.spinner("Agents soch rahe hain…"):
                decision, state = bot.decide(d_sym)
            m = st.columns(4)
            m[0].metric("Action", decision.action.value)
            m[1].metric("Rating", decision.rating.value)
            m[2].metric("Target weight", f"{decision.target_weight:+.2%}")
            m[3].metric("Conviction", f"{decision.conviction:.2f}")
            st.info(f"**Reason:** {decision.reason} · Approved: {'✅' if decision.approved else '❌'}")
            st.area_chart(state.ohlcv['close'].tail(120).rename('price'), height=200, color="#16C784")
            st.markdown("**📋 Analysts**")
            st.dataframe(pd.DataFrame([{
                "analyst": r.analyst, "stance": round(r.stance, 2),
                "confidence": round(r.confidence, 2), "summary": r.summary} for r in state.reports]),
                use_container_width=True, hide_index=True)
            a, b = st.columns(2)
            with a:
                st.markdown("**🐂🐻 Investment debate**")
                for t in state.investment_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:160]}")
            with b:
                st.markdown("**⚖️ Risk debate**")
                for t in state.risk_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:150]}")
        except Exception as e:
            st.error(f"Error: {e}. Try 'mock'.")

# ----------------------------------------------------------------- BACKTEST
with tab_bt:
    st.subheader("📊 Walk-forward backtest — NET of costs")
    c = st.columns([2, 1, 1])
    b_sym = c[0].text_input("Symbol", "BTC-USD", key="b_sym")
    b_prov = c[1].selectbox("Data", ["mock", "yfinance"], index=0, key="b_prov")
    b_run = c[2].button("📊 Run backtest", use_container_width=True)
    if b_run or "bt_done" not in st.session_state:
        st.session_state["bt_done"] = True
        try:
            s = Settings(mode="mock", data_provider=b_prov)
            ohlcv = load_ohlcv(b_sym, b_prov, 400)
            bt = Backtester(s)
            with st.spinner("Backtesting…"):
                rep = bt.run(b_sym, ohlcv)
            k = st.columns(4)
            k[0].metric("Net Sharpe", rep["sharpe"])
            k[1].metric("Total return", f"{rep['total_return']:.1%}")
            k[2].metric("Max drawdown", f"{rep['max_drawdown']:.1%}")
            k[3].metric("Beats buy&hold", "✅" if rep["beats_buy_and_hold"] else "❌")
            st.markdown("**Equity curve — strategy vs buy & hold (net of costs)**")
            st.line_chart(bt.last_curves, height=300, color=["#16C784", "#8892A0"])
            crit = [f for f in rep["overfit_flags"] if f["severity"] == "critical"]
            st.error(f"⚠️ Overfit flags: {[f['message'] for f in crit]}") if crit else \
                st.success("No critical overfit flags (net-of-cost, leakage-checked).")
        except Exception as e:
            st.error(f"Error: {e}. Try 'mock'.")

# ----------------------------------------------------------------- CARRY
with tab_carry:
    st.subheader("💰 The honest path: funding carry")
    st.markdown(
        "Delta-neutral carry = **spot long + perp short**. Market upar jaye ya neeche, "
        "hedge cancel ho jaata hai — tum sirf **funding payment** collect karte ho (perp shorts "
        "tumhe pay karte hain jab funding positive ho). Ye **prediction nahi, cash flow** hai.")
    if st.button("🔄 Fetch live funding rates (Binance)"):
        from aitrader.research.funding_data import latest_funding_rates
        with st.spinner("Fetching…"):
            rates = latest_funding_rates(CARRY_SYMS)
        if all(v is None for v in rates.values()):
            st.warning("Live funding unavailable on this host (Binance geo-block on cloud). "
                       "Neeche humare measured backtest numbers dekho — wo real hain.")
        else:
            rows = []
            for s, r in rates.items():
                if r is None:
                    continue
                rows.append({"coin": s.replace("USDT", ""), "funding_8h": f"{r*100:.4f}%",
                             "annualized_carry": f"{r*3*365*100:.1f}%"})
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.caption("Annualized = funding × 3/day × 365. Gross — costs aur capital-efficiency abhi minus nahi.")

    st.markdown("**Humare measured results (2y, BTC/ETH/SOL/BNB, pessimistic costs):**")
    st.dataframe(pd.DataFrame([
        {"Version": "Selective (threshold)", "Net APR": "~0.8%/yr", "Gauntlet": "5/6 — fragile"},
        {"Version": "Continuous", "Net APR": "-4.1%/yr", "Gauntlet": "2/6 — over-trades"},
    ]), use_container_width=True, hide_index=True)
    st.info("**Honest 5–10% ka raasta:** unleveraged carry chhota (~0.8%) hai. Realistic 5–10% ke liye "
            "**3–5x leverage + capital efficiency + better fees** chahiye (business/capital decision, "
            "code nahi). Pehla kadam: **selective carry ko mahino paper-trade** karke confirm karo.")
    st.warning("⚠️ Leverage risk badhata hai. Exchange outage/extreme vol me hedge tootta hai. "
               "Sirf utna jo doob jaye toh farak na pade.")

# ----------------------------------------------------------------- LEARNINGS
with tab_learn:
    st.subheader("🧪 Experiments + Validation Gauntlet")
    st.dataframe(pd.DataFrame([
        {"Candidate": "ML price prediction", "Checks": "—", "Verdict": "❌ no edge"},
        {"Candidate": "Meta-labeling", "Checks": "—", "Verdict": "❌ didn't help"},
        {"Candidate": "Funding carry (selective)", "Checks": "5/6", "Verdict": "⚠️ real but fragile+tiny"},
        {"Candidate": "Funding carry (continuous)", "Checks": "2/6", "Verdict": "❌ over-trades"},
        {"Candidate": "Time-series momentum", "Checks": "3/6", "Verdict": "❌ no real edge"},
    ]), use_container_width=True, hide_index=True)
    st.markdown("**Sabak:** gauntlet real vs fake edge distinguish karta hai. Abhi koi deployable "
                "edge nahi — aur wo bhi imaandaar result hai. Yehi system tumhe fake edge deploy "
                "karke doobne se bachata hai.")
    st.warning("⚠️ Koi bhi bot 100% profit guarantee nahi karta. Yeh research/learning tool hai.")
