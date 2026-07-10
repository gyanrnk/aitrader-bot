"""Page 2 — Bot dashboard: architecture diagram, live agent decision, backtest."""
from __future__ import annotations

import pandas as pd
import streamlit as st

from aitrader.config import Settings
from aitrader.runner import TradingBot
from aitrader.data import get_provider
from aitrader.backtest import Backtester

st.set_page_config(page_title="Bot Dashboard", page_icon="🤖", layout="wide")

st.title("🤖 aitrader — AI Trading Architecture")
st.caption("Dekho humara bot andar kya karta hai. Mock mode = free, no keys.")

tab_arch, tab_decide, tab_back, tab_learn = st.tabs(
    ["🏗️ Architecture", "🧠 Live Decision", "📊 Backtest", "🧪 What we learned"])

ARCH_DOT = r"""
digraph G {
  rankdir=TB; bgcolor="transparent";
  node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11, color="#00000000"];
  edge [color="#888888", fontname="Arial", fontsize=9];
  subgraph cluster_data { label="1 · DATA (free)"; style=rounded; color="#4C8BF5";
    d1 [label="Market data\n(yfinance / mock)", fillcolor="#DCE9FF"];
    d2 [label="Alt-data\nFunding rate (Binance)", fillcolor="#DCE9FF"];
    d3 [label="🔒 Leakage firewall\n(no future data)", fillcolor="#DCE9FF"]; }
  subgraph cluster_model { label="2 · FEATURES + ML"; style=rounded; color="#8E5BE8";
    m1 [label="Indicators\nRSI/MACD/vol", fillcolor="#EBDDFB"];
    m2 [label="Triple-barrier\nlabels", fillcolor="#EBDDFB"];
    m3 [label="LightGBM\nP(up-move)", fillcolor="#EBDDFB"]; }
  subgraph cluster_agents { label="3 · AGENT DEBATE"; style=rounded; color="#2F9E44";
    a1 [label="4 Analysts\n(mkt/news/senti/fund)", fillcolor="#D7F5DE"];
    a2 [label="🐂 Bull  vs  Bear 🐻\n(bounded debate)", fillcolor="#D7F5DE"];
    a3 [label="Trader\nproposal", fillcolor="#D7F5DE"];
    a4 [label="Risk debate\nAggr/Cons/Neutral", fillcolor="#D7F5DE"];
    a5 [label="Portfolio Mgr\nBuy/Sell/Hold", fillcolor="#D7F5DE"]; }
  mem [label="🧠 MEMORY\nlayered + decay\n+ reflection", fillcolor="#FFE8CC", color="#E8890C"];
  subgraph cluster_exec { label="4 · RISK + EXECUTION"; style=rounded; color="#E03131";
    r1 [label="Position sizing\n(hard caps)", fillcolor="#FFE0E0"];
    r2 [label="Broker\npaper / ccxt", fillcolor="#FFE0E0"]; }
  gate [label="🚦 DISCIPLINE GATE\nnet-of-cost · beat baselines · overfit check",
        fillcolor="#343A40", fontcolor="white"];
  d1 -> d3; d2 -> d3; d3 -> m1 -> m2 -> m3 -> a1;
  a1 -> a2 -> a3 -> a4 -> a5 -> r1 -> r2;
  mem -> a2 [label="recall", style=dashed, color="#E8890C"];
  a5 -> mem [label="reflect", style=dashed, color="#E8890C"];
  r2 -> gate [style=dotted]; m3 -> gate [style=dotted, label="validated"];
}
"""

with tab_arch:
    st.subheader("Poora system, ek nazar me")
    st.graphviz_chart(ARCH_DOT, use_container_width=True)
    c1, c2 = st.columns(2)
    with c1:
        st.markdown(
            "**Kaise chalta hai (fast loop — FREE, har bar):**\n"
            "1. Data aata hai → firewall future-data block karta hai\n"
            "2. Features + LightGBM → up-move ki probability\n"
            "3. Analysts → Bull/Bear **debate** → Trader → Risk debate → decision\n"
            "4. Risk caps → paper broker (safe)")
    with c2:
        st.markdown(
            "**Do khaas cheezein:**\n"
            "- 🧠 **Memory** har trade se seekhta hai (decay + reflection)\n"
            "- 🚦 **Discipline gate**: strategy tabhi live jaati hai jab net-of-cost "
            "profit de aur overfit na ho\n\n"
            "**LLM sirf slow-loop me** — per-bar decision FREE rehta hai.")

with tab_decide:
    st.subheader("Ek live decision — poora reasoning dekho")
    col = st.columns([2, 1, 1])
    symbol = col[0].text_input("Symbol", "BTC-USD")
    provider = col[1].selectbox("Data", ["mock", "yfinance"], index=0)
    run = col[2].button("▶️ Run decision", use_container_width=True)
    st.caption("Tip: 'mock' = instant example. Neeche 4 analysts ki raay + Bull/Bear debate dikhega.")
    if run or "decided_once" not in st.session_state:
        st.session_state["decided_once"] = True
        try:
            bot = TradingBot(Settings(mode="mock", data_provider=provider))
            with st.spinner("Agents soch rahe hain…"):
                decision, state = bot.decide(symbol)
            d = decision
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Action", d.action.value)
            m2.metric("Rating", d.rating.value)
            m3.metric("Target weight", f"{d.target_weight:+.2%}")
            m4.metric("Conviction", f"{d.conviction:.2f}")
            st.info(f"**Reason:** {d.reason}  ·  Approved: {'✅' if d.approved else '❌'}")
            st.markdown("**📋 Analyst reports**")
            st.dataframe(pd.DataFrame([{
                "analyst": r.analyst, "stance": round(r.stance, 2),
                "confidence": round(r.confidence, 2), "summary": r.summary,
            } for r in state.reports]), use_container_width=True, hide_index=True)
            cA, cB = st.columns(2)
            with cA:
                st.markdown("**🐂🐻 Investment debate**")
                for t in state.investment_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:180]}")
                st.caption(state.investment_plan)
            with cB:
                st.markdown("**⚖️ Risk debate**")
                for t in state.risk_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:160]}")
                if state.risk_decision:
                    st.caption(f"PM: {state.risk_decision.rationale} · {state.risk_decision.adjustments}")
            with st.expander("🔢 Features at decision time"):
                st.json({k: round(v, 4) for k, v in state.features.items()})
        except Exception as e:
            st.error(f"Error: {e}. yfinance flaky ho toh 'mock' try karo.")

with tab_back:
    st.subheader("Walk-forward backtest — NET of costs")
    c = st.columns([2, 1, 1])
    bt_symbol = c[0].text_input("Symbol ", "BTC-USD", key="bt")
    bt_provider = c[1].selectbox("Data ", ["mock", "yfinance"], index=0, key="btp")
    bt_run = c[2].button("📊 Run backtest", use_container_width=True)
    if bt_run:
        try:
            s = Settings(mode="mock", data_provider=bt_provider)
            ohlcv = get_provider(s).ohlcv(bt_symbol, lookback=400)
            with st.spinner("Backtesting…"):
                rep = Backtester(s).run(bt_symbol, ohlcv)
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Net Sharpe", rep["sharpe"])
            k2.metric("Total return", f"{rep['total_return']:.1%}")
            k3.metric("Max drawdown", f"{rep['max_drawdown']:.1%}")
            k4.metric("Beats buy&hold", "✅" if rep["beats_buy_and_hold"] else "❌")
            st.markdown("**Baselines ko beat kiya?**")
            st.dataframe(pd.DataFrame(
                [{"baseline": k, "beaten": "✅" if v else "❌"}
                 for k, v in rep["beats_baselines"].items()]),
                use_container_width=True, hide_index=True)
            crit = [f for f in rep["overfit_flags"] if f["severity"] == "critical"]
            if crit:
                st.error(f"⚠️ Overfit red flags: {[f['message'] for f in crit]}")
            else:
                st.success("No critical overfit flags. (Net-of-cost, leakage-checked.)")
        except Exception as e:
            st.error(f"Error: {e}. 'mock' try karo agar yfinance slow ho.")

with tab_learn:
    st.subheader("Experiments + Validation Gauntlet — humne kya seekha")
    st.markdown("**Signal experiments:**")
    st.dataframe(pd.DataFrame([
        {"Approach": "Price ML (prediction)", "Result": "no edge (Sharpe ~0)", "Why": "price near-random"},
        {"Approach": "Meta-labeling", "Result": "❌ didn't help", "Why": "can't create edge that isn't there"},
        {"Approach": "Funding carry (cash flow)", "Result": "real but tiny (~0.76%/yr)", "Why": "real payment, not prediction"},
    ]), use_container_width=True, hide_index=True)

    st.markdown("**Stage 4 Validation Gauntlet (6 free checks — 'guilty until proven innocent'):**")
    st.dataframe(pd.DataFrame([
        {"Candidate": "Funding carry", "Checks passed": "5/6", "Failed on": "param_plateau (fragile)", "Deployable": "❌"},
        {"Candidate": "Time-series momentum", "Checks passed": "3/6", "Failed on": "PBO + DSR + falsification", "Deployable": "❌"},
    ]), use_container_width=True, hide_index=True)
    st.markdown(
        "**Sabak:** gauntlet dono ko sahi distinguish karta hai — carry (real cash flow) sirf "
        "fragility pe fail hua, momentum (prediction) 3 deep checks pe. **Abhi koi deployable "
        "edge nahi** — aur wo bhi ek imaandaar result hai. Yehi system tumhe fake edge deploy "
        "karke doobने se bachata hai.")
    st.warning("⚠️ Koi bhi bot 100% profit guarantee nahi karta. Yeh R&D hai, ATM nahi.")
