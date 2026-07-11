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
st.caption("Ek research trading bot — test karta hai ki koi strategy SACH me paisa banati hai ya "
           "nahi, bina asli paisa lagaye. Neeche guide kholo.")

with st.expander("❓ Ye dashboard kaise padhein — simple guide (pehle ye kholo)"):
    st.markdown("""
| Tab | Simple me kya dikhata hai |
|---|---|
| 📈 **Markets** | Kisi coin ka **live price chart** + basic numbers |
| 🧠 **Live Decision** | Bot ka **ek faisla** (BUY/SELL/HOLD) + **kyun** (AI agents ki debate) |
| 📊 **Backtest** | Purane data pe strategy chalaake **profit/loss** — *fees ke baad* |
| 💰 **Carry** | Humari **asli strategy** (funding se paisa) + honest result |
| 📡 **Signals** | 24/7 data se **signals** + **REAL accuracy** (hafton me banti hai) |
| 🧪 **Learnings** | Humne **kya-kya try kiya** aur kya nikla |

**Asli kaam yahan hota hai:** 📊 Backtest, 💰 Carry, 📡 Signals.
**"mock" data = nakli/instant (free test); "yfinance" = real (cloud pe kabhi slow).**
**Ye report TUMHARE liye hai** — jaano strategy chalegi ya doobegi. *(Abhi tak koi guaranteed
profit nahi mila — aur wo bhi imaandaar result hai.)*
""")

tabs = st.tabs(["📈 Markets", "🧠 Live Decision", "📊 Backtest",
                "💰 Carry (5–10% path)", "📡 Signals", "🧪 Learnings"])
tab_mkt, tab_dec, tab_bt, tab_carry, tab_sig, tab_learn = tabs

CARRY_SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]


@st.cache_data(ttl=300, show_spinner=False)
def load_ohlcv(symbol: str, provider: str, n: int = 400):
    return get_provider(Settings(data_provider=provider)).ohlcv(symbol, lookback=n)


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
    st.caption("Bot ek symbol pe **BUY/SELL/HOLD** decide karta hai. Neeche dekho: 4 AI analysts ki "
               "ray → 🐂 Bull (tejī) vs 🐻 Bear (mandī) debate → risk debate → final faisla + kyun.")
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
    st.caption("Strategy ko **purane data pe** chalate hain (fees minus karke). **Equity curve** upar "
               "jaye = profit. 🟢 line = humari strategy, ⚪ line = 'bas coin kharid ke rakhna'. "
               "Strategy grey se upar ho tabhi wo useful hai.")
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

# ----------------------------------------------------------------- SIGNALS
with tab_sig:
    st.subheader("📡 Live Signals + honest forward accuracy")
    st.caption("24/7 collector se banaye signals. Accuracy FORWARD measure hoti hai "
               "(prediction pehle, outcome baad me) — nakli backtest nahi.")
    try:
        from aitrader.collector import analytics
        hist = analytics.load_history()
    except Exception as e:
        hist, _err = None, e
        st.error(f"Could not load collected data: {e}")

    if hist is None or hist.empty:
        st.info("Abhi tak collected data nahi. Collector (GitHub Action) har 30 min pe jama kar "
                "raha hai — thodi der me yahan dikhega. Actions tab → 'Run workflow' se turant test karo.")
    else:
        n_snaps = hist["ts"].nunique()
        span_h = (hist["ts"].max() - hist["ts"].min()).total_seconds() / 3600
        c = st.columns(3)
        c[0].metric("Snapshots", f"{n_snaps}")
        c[1].metric("Symbols", f"{hist['symbol'].nunique()}")
        c[2].metric("Time span", f"{span_h:.1f} h")

        rows = []
        for sym, g in hist.groupby("symbol"):
            sig = analytics.compute_signal(g)
            if sig:
                rows.append({"symbol": sym, "signal": sig["signal"], "prob_up": sig["prob_up"],
                             "funding_z": sig["funding_z"], "momentum": round(sig["mom"], 4)})
        if rows:
            st.markdown("**Current signals**")
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info(f"Signals ~20 snapshots ke baad start honge (abhi {n_snaps}). Roughly ~10 ghante.")

        try:
            piv = hist.pivot_table(index="ts", columns="symbol", values="funding") * 24 * 365 * 100
            st.markdown("**Funding rate over time (annualized %, Kraken hourly)**")
            st.line_chart(piv, height=240)
        except Exception:
            pass

        st.markdown("**Forward accuracy — matured predictions only (the HONEST number)**")
        score = analytics.score_predictions(hist)
        if score.get("scored", 0) == 0:
            st.warning(f"{score.get('note')}. Accuracy 1–2 hafte me real hogi — abhi samples bahut kam.")
        else:
            k = st.columns(3)
            k[0].metric("Predictions scored", score["scored"])
            k[1].metric("Hit rate", f"{score['hit_rate']:.1%}")
            k[2].metric("Expectancy/call", f"{score['avg_return_per_call']:+.3%}",
                        "profitable" if score["expectancy_positive"] else "not yet")
            st.caption("Hit-rate akela profit nahi — **expectancy** (net return per call) decide karta hai.")
        st.warning("⚠️ Realistic accuracy ~50–55%. 90% dikhe toh leakage. Koi profit guarantee nahi.")

        # --- forward paper-trade equity (fake money, live data — THE real test) ---
        st.markdown("**📈 Paper P&L — fake ₹, live data, forward (the real test)**")
        eq_path = analytics.ROOT / "data" / "paper_equity.csv"
        if eq_path.exists():
            eq = pd.read_csv(eq_path)
            eq["ts"] = pd.to_datetime(eq["ts"], utc=True)
            eq = eq.set_index("ts")
            start = 10_000.0
            cur = float(eq["equity"].iloc[-1])
            cc = st.columns(3)
            cc[0].metric("Fake equity", f"${cur:,.0f}", f"{cur/start-1:+.2%}")
            cc[1].metric("Steps", f"{len(eq)}")
            cc[2].metric("Open positions", f"{int(eq['active_positions'].iloc[-1])}")
            st.line_chart(eq["equity"], height=240, color="#16C784")
            st.caption("Start $10,000 (nakli). Ye curve upar jaye = signals live paisa bana rahe. "
                       "Hafton ka data chahiye — abhi shuruaat hai.")
        else:
            st.info("Paper-trade abhi start nahi hua — collector chalne ke baad equity curve banega.")

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
