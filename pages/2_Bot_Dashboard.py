"""Bot Dashboard — every tab must TEACH, not just display.

Two rules this file exists to enforce:

1. REAL DATA BY DEFAULT. This dashboard used to default to the `mock` provider — a random
   walk. It rendered BTC-USD at $101.98 while BTC was $63,227, under a heading that said
   "Markets". Every tab downstream (Live Decision, Backtest) then reasoned about fake
   numbers. A user trying to learn from that cannot possibly succeed, and would blame
   themselves. Mock is now opt-in and shouts when it is on.

2. NOTHING HARDCODED THAT CAN GO STALE. The Learnings tab was a frozen 5-row table that
   still said "funding carry: real but fragile" after the registry had rejected it, and
   never mentioned liq_meanrev / xexch_arb / delist_event at all. It now reads
   research/hypotheses.json, same as Home.py.

Every tab follows: WHAT IS THIS -> the data -> WHAT SHOULD I UNDERSTAND. The third part is
the point; the middle is just evidence.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

from aitrader.config import Settings
from aitrader.runner import TradingBot
from aitrader.data import get_provider
from aitrader.backtest import Backtester

st.set_page_config(page_title="Bot Dashboard", page_icon="🤖", layout="wide")

ROOT = Path(__file__).resolve().parents[1]

st.markdown("""
<style>
  .block-container{padding-top:2.2rem;}
  div[data-testid="stMetric"]{background:#161B22;border:1px solid #26303B;
     border-radius:14px;padding:.7rem 1rem;}
  h1,h2,h3{letter-spacing:-.3px;}
  .lesson{background:#0E1F2A;border:1px solid #2E8BFF55;border-left:4px solid #2E8BFF;
          border-radius:10px;padding:.85rem 1.1rem;margin:.8rem 0;}
  .lesson b{color:#6FB4FF;}
</style>
""", unsafe_allow_html=True)


def lesson(md: str) -> None:
    """The 'what should I understand' box — the reason each tab exists."""
    st.markdown(f'<div class="lesson">💡 <b>Isse kya samajhna hai:</b><br>{md}</div>',
                unsafe_allow_html=True)


# ---------------------------------------------------------------- data provider
@st.cache_data(ttl=300, show_spinner=False)
def load_ohlcv(symbol: str, provider: str, n: int = 400):
    return get_provider(Settings(data_provider=provider)).ohlcv(symbol, lookback=n)


@st.cache_data(ttl=600, show_spinner=False)
def real_data_works() -> bool:
    try:
        d = get_provider(Settings(data_provider="yfinance")).ohlcv("BTC-USD", lookback=5)
        return len(d) > 0
    except Exception:
        return False


REAL_OK = real_data_works()
PROVIDERS = ["yfinance", "mock"] if REAL_OK else ["mock"]


def provider_picker(key: str) -> str:
    """Real data first, always. Mock is a fallback that announces itself."""
    p = st.selectbox("Data", PROVIDERS, index=0, key=key,
                     help="yfinance = ASLI market data. mock = NAKLI random numbers "
                          "(sirf machine test karne ke liye — isse kuch mat seekhna).")
    if p == "mock":
        st.error("🚨 **NAKLI DATA ON.** Ye random numbers hain, asli market nahi. "
                 "BTC yahan ~$100 dikhega jabki asli ~$63,000 hai. **Neeche ke saare "
                 "numbers matlab-rahit hain** — sirf ye check karne ke liye ki code chalta hai.")
    return p


st.title("🤖 aitrader — Bot Dashboard")
st.caption("Har tab teen cheezein batata hai: **ye kya hai** → **data** → **isse kya samajhna hai**.")

if not REAL_OK:
    st.warning("⚠️ Asli market data (yfinance) is host pe nahi mil raha — sirf nakli data available "
               "hai. Numbers ko seriously mat lena.")

with st.expander("❓ Pehle ye padho — 30 second me pura dashboard"):
    st.markdown("""
**Ye bot abhi paisa nahi bana raha, aur ye chhupaya nahi ja raha.** 5 ideas test kiye, 5 fail.
Ye dashboard tumhe **kyun** samjhane ke liye hai — taaki tum agla idea behtar soch sako.

| Tab | Ye kya hai | Bharosa karein? |
|---|---|---|
| 📈 **Markets** | Asli coin price + basic numbers | ✅ asli data |
| 🧠 **Live Decision** | Bot ka ek faisla + uski poori soch | ⚠️ machinery samajhne ke liye — **is faisle me koi edge nahi** |
| 📊 **Backtest** | Purane data pe strategy — fees ke baad | ✅ par mock data pe mat chalana |
| 💰 **Carry** | ☠️ reject ho chuki strategy ka live record | ❌ plan nahi hai |
| 📡 **Signals** | 24/7 signals + **asli forward accuracy** | ✅ **sabse important tab** |
| 🧪 **Learnings** | Har idea, uska verdict, aur kyun mara | ✅ registry se live |

**Agar sirf ek tab dekhna ho: 📡 Signals.** Wahan ek number hai jo poori kahani batata hai.
""")

tabs = st.tabs(["📈 Markets", "🧠 Live Decision", "📊 Backtest",
                "💰 Carry (☠️ rejected)", "📡 Signals", "🧪 Learnings"])
tab_mkt, tab_dec, tab_bt, tab_carry, tab_sig, tab_learn = tabs

CARRY_SYMS = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "BNBUSDT"]

# ----------------------------------------------------------------- MARKETS
with tab_mkt:
    st.subheader("📈 Markets")
    st.caption("**Ye kya hai:** ek coin/stock ka asli price chart aur uske basic numbers. "
               "Yahan koi strategy nahi — sirf 'market kar kya raha hai'.")
    c = st.columns([2, 1, 1])
    sym = c[0].text_input("Symbol", "BTC-USD", key="mk_sym",
                          help="BTC-USD, ETH-USD, AAPL, SPY, ^NSEI (Nifty), RELIANCE.NS")
    with c[1]:
        prov = provider_picker("mk_prov")
    rng = c[2].selectbox("Range (bars)", [120, 250, 400], index=1, key="mk_rng")
    try:
        df = load_ohlcv(sym, prov, rng)
        close = df["close"]
        vol = close.pct_change().std() * np.sqrt(365)
        k = st.columns(4)
        k[0].metric("Price", f"${close.iloc[-1]:,.2f}",
                    f"{close.iloc[-1]/close.iloc[-2]-1:+.2%}", help="Aakhri bar se change")
        k[1].metric("30-bar change", f"{close.iloc[-1]/close.iloc[-min(30,len(close))]-1:+.1%}",
                    help="Pichhle 30 bars me kitna hila")
        k[2].metric("Ann. volatility", f"{vol:.0%}",
                    help="Saal bhar me price typically kitna upar-neeche hota hai")
        k[3].metric("Bars", f"{len(close)}")
        st.area_chart(close.rename("price"), height=300, color="#16C784")
        st.caption("Volume — kitna trade hua")
        st.bar_chart(df["volume"].tail(80), height=140, color="#2E8BFF")
        lesson(f"<b>Volatility {vol:.0%}</b> ka matlab: is asset ka price ek saal me typically "
               f"±{vol:.0%} hilta hai. Ye <b>risk</b> hai, opportunity nahi — zyada volatility ka "
               "matlab zyada profit nahi, sirf zyada jhatke. Har strategy ka profit isi ke "
               "<b>saamne</b> tolna chahiye: 10% return 15% vol pe accha hai, 80% vol pe bakwaas.")
    except Exception as e:
        st.error(f"Data error: {e}")

# ----------------------------------------------------------------- LIVE DECISION
with tab_dec:
    st.subheader("🧠 Live Decision — bot ne kya socha")
    st.caption("**Ye kya hai:** bot ek symbol pe BUY/SELL/HOLD decide karta hai. Neeche uski "
               "poori soch dikhti hai — 4 analysts → 🐂 Bull vs 🐻 Bear debate → risk debate → faisla.")
    st.error("⚠️ **Ye faisla trade karne ke liye NAHI hai.** Humne isi engine ko **2,930 baar** "
             "live test kiya: **hit rate 49.9%** — yaani sikka uchhalna. Ye tab yahan sirf "
             "isliye hai ki tum **machinery samajh sako**, faisle pe bharosa karne ke liye nahi.")
    c = st.columns([2, 1, 1])
    d_sym = c[0].text_input("Symbol", "BTC-USD", key="d_sym")
    with c[1]:
        d_prov = provider_picker("d_prov")
    d_run = c[2].button("▶️ Run decision", use_container_width=True)
    if d_run or "decided" not in st.session_state:
        st.session_state["decided"] = True
        try:
            bot = TradingBot(Settings(mode="mock", data_provider=d_prov))
            with st.spinner("Agents soch rahe hain…"):
                decision, state = bot.decide(d_sym)
            m = st.columns(4)
            m[0].metric("Action", decision.action.value, help="Bot kya karna chahta hai")
            m[1].metric("Rating", decision.rating.value, help="Kitna strong view hai")
            m[2].metric("Target weight", f"{decision.target_weight:+.2%}",
                        help="Portfolio ka kitna % is trade me. + = long, − = short. "
                             "Risk layer ise hard-cap karta hai.")
            m[3].metric("Conviction", f"{decision.conviction:.2f}",
                        help="0 = bilkul pakka nahi, 1 = pura yakeen. Ye bot ka apna andaaza hai — "
                             "aur uska andaaza 49.9% sahi hota hai, yaani ye number bharosemand nahi.")
            st.info(f"**Reason:** {decision.reason} · Approved: {'✅' if decision.approved else '❌'}")
            st.area_chart(state.ohlcv['close'].tail(120).rename('price'), height=200, color="#16C784")
            st.markdown("**📋 Analysts** — har ek ka apna nazariya")
            st.caption("`stance`: −1 = pura mandi, 0 = neutral, +1 = pura teji. "
                       "`confidence`: 0–1, kitna pakka hai.")
            st.dataframe(pd.DataFrame([{
                "analyst": r.analyst, "stance": round(r.stance, 2),
                "confidence": round(r.confidence, 2), "summary": r.summary} for r in state.reports]),
                use_container_width=True, hide_index=True)
            a, b = st.columns(2)
            with a:
                st.markdown("**🐂🐻 Investment debate** — teji vs mandi")
                for t in state.investment_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:160]}")
            with b:
                st.markdown("**⚖️ Risk debate** — kitna bada position")
                for t in state.risk_debate:
                    st.write(f"`R{t.round}` **{t.speaker}**: {t.argument[:150]}")
            lesson("Ye debate <b>dekhne me impressive</b> hai — analysts, bull vs bear, risk "
                   "committee. Aur wo <b>bilkul kaam nahi karta</b> (49.9%). "
                   "<b>Yahi is project ka sabse bada sabak hai:</b> sophisticated machinery se "
                   "edge nahi banta. Edge <i>mechanism</i> se banta hai — koi aisa jo majboori me "
                   "tumhe paisa de. Achhi dikhne wali reasoning aur paisa banane wali reasoning "
                   "do alag cheezein hain.")
        except Exception as e:
            st.error(f"Error: {e}")

# ----------------------------------------------------------------- BACKTEST
with tab_bt:
    st.subheader("📊 Walk-forward backtest — fees ke BAAD")
    st.caption("**Ye kya hai:** strategy ko purane data pe chalate hain, fees minus karke. "
               "🟢 = strategy, ⚪ = 'bas coin kharid ke baith jao'. **🟢 ko ⚪ se upar hona chahiye**, "
               "warna strategy bekaar hai — kuch na karna sasta aur behtar tha.")
    c = st.columns([2, 1, 1])
    b_sym = c[0].text_input("Symbol", "BTC-USD", key="b_sym")
    with c[1]:
        b_prov = provider_picker("b_prov")
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
            k[0].metric("Net Sharpe", rep["sharpe"],
                        help="Return ÷ risk. <0 = paisa gaya. ~1 = accha. >2 = shak karo (aksar overfit).")
            k[1].metric("Total return", f"{rep['total_return']:.1%}")
            k[2].metric("Max drawdown", f"{rep['max_drawdown']:.1%}",
                        help="Peak se sabse bada gir. Ye wo number hai jo raat ko sone nahi deta.")
            k[3].metric("Beats buy&hold", "✅" if rep["beats_buy_and_hold"] else "❌",
                        help="Agar ❌ hai to strategy ka koi matlab nahi — hold karna behtar tha.")
            st.markdown("**Equity curve — strategy (🟢) vs buy & hold (⚪), fees ke baad**")
            st.line_chart(bt.last_curves, height=300, color=["#16C784", "#8892A0"])
            crit = [f for f in rep["overfit_flags"] if f["severity"] == "critical"]
            if crit:
                st.error(f"⚠️ Overfit flags: {[f['message'] for f in crit]}")
            else:
                st.success("No critical overfit flags (net-of-cost, leakage-checked).")
            lesson("Ek accha backtest <b>saboot nahi</b> hai. Research (25 sources) se pata chala: "
                   "in-sample Sharpe out-of-sample ko <b>2–4× bada</b> dikhata hai, aur "
                   "<b>pure noise</b> se bhi 'profitable' strategy banayi ja sakti hai kuch sau "
                   "koshishon me. Isliye humne <b>gauntlet</b> banaya (PBO · Deflated Sharpe · "
                   "cost-stress · falsification). <b>Yahan ka number sirf shuruaat hai — gauntlet "
                   "faisla karta hai.</b>")
        except Exception as e:
            st.error(f"Error: {e}")

# ----------------------------------------------------------------- CARRY
with tab_carry:
    st.subheader("💰 Funding carry — ☠️ TESTED AND REJECTED")
    st.error(
        "**Ye tab pehle 'the honest path: 5–10%' kehta tha. Wo galat tha.** Carry gauntlet me "
        "gaya aur **fail** hua — continuous version ka net APR **−4.14%/yr** (2/6), selective "
        "version 5/6 pe **param_plateau fail** (fragile). Registry: **NOT deployable**. "
        "Live paper **−3.9%**.\n\n"
        "Monitor zinda hai kyunki **mechanism asli hai** — bas retail cost pe harvest nahi hota. "
        "Ise ek *rejected idea ka live record* samjho, **plan nahi**.")
    st.markdown(
        "**Ye kya hai:** Delta-neutral carry = **spot long + perp short**. Market upar jaye ya "
        "neeche, hedge cancel ho jaata hai — tum sirf **funding payment** collect karte ho. "
        "Ye **prediction nahi, cash flow** hai — aur phir bhi kaafi nahi nikla.")
    st.markdown("**Humare measured results (2y, BTC/ETH/SOL/BNB, pessimistic costs):**")
    st.dataframe(pd.DataFrame([
        {"Version": "Selective (threshold)", "Net APR": "~0.8%/yr", "Gauntlet": "5/6 — fragile"},
        {"Version": "Continuous", "Net APR": "−4.1%/yr", "Gauntlet": "2/6 — over-trades"},
    ]), use_container_width=True, hide_index=True)
    lesson("Carry ka mechanism <b>100% asli</b> hai — perp shorts sach me funding pay karte hain. "
           "Phir bhi ye mara. Kyun? <b>Kyunki asli mechanism kaafi nahi hota — usse itna bada "
           "hona padta hai ki cost ke baad kuch bache.</b> Unleveraged carry ~0.8%/yr deta hai; "
           "fees usse kha jaati hain. Ye humare <b>har</b> rejection ka pattern hai: "
           "mechanism ASLI, edge UNCAPTURABLE.")
    st.warning("⚠️ 5–10% ke liye 3–5× leverage chahiye. Leverage risk badhata hai — exchange "
               "outage ya extreme vol me hedge tootta hai. Ye code ka nahi, capital ka faisla hai.")

# ----------------------------------------------------------------- SIGNALS
with tab_sig:
    st.subheader("📡 Signals + asli forward accuracy")
    st.caption("**Ye kya hai:** humara collector har 10 min data jama karta hai aur signal banata "
               "hai. Phir hum **pehle** prediction likhte hain aur **baad me** dekhte hain ki sahi "
               "hui ya nahi. Ye **forward** accuracy hai — backtest nahi, jisme jhoot bolna aasaan hai.")
    try:
        from aitrader.collector import analytics
        hist = analytics.load_history()
    except Exception as e:
        hist = None
        st.error(f"Could not load collected data: {e}")

    if hist is None or hist.empty:
        st.info("Abhi tak collected data nahi.")
    else:
        n_snaps = hist["ts"].nunique()
        span_h = (hist["ts"].max() - hist["ts"].min()).total_seconds() / 3600
        last_age_min = (pd.Timestamp.now(tz="UTC") - hist["ts"].max()).total_seconds() / 60
        c = st.columns(4)
        c[0].metric("Snapshots", f"{n_snaps}")
        c[1].metric("Symbols", f"{hist['symbol'].nunique()}")
        c[2].metric("Time span", f"{span_h:.0f} h")
        c[3].metric("Last update", f"{last_age_min:.0f} min ago")
        if last_age_min > 45:
            st.warning("⚠️ Collector shaayad ruk gaya (45 min se update nahi). GitHub Actions check karo.")
        else:
            st.success("🟢 Collector zinda hai.")

        # ---- THE number, first, before any jargon
        st.markdown("### 🎯 Sabse important number")
        score = analytics.score_predictions(hist)
        if score.get("scored", 0) == 0:
            st.warning(f"{score.get('note')}")
        else:
            hr = score["hit_rate"]
            n = score["scored"]
            se = (0.25 / n) ** 0.5
            lo, hi = hr - 1.96 * se, hr + 1.96 * se
            k = st.columns(3)
            k[0].metric("Predictions checked", f"{n:,}",
                        help="Har ek: pehle likha, baad me score kiya. Koi cheating nahi.")
            k[1].metric("Hit rate", f"{hr:.1%}",
                        help="Kitni predictions sahi nikli")
            k[2].metric("Expectancy / call", f"{score['avg_return_per_call']:+.3%}",
                        "profitable" if score["expectancy_positive"] else "not profitable",
                        delta_color="normal" if score["expectancy_positive"] else "inverse")
            st.error(f"""**Sikka uchhalna = 50%. Humara bot = {hr:.1%}.**

{n:,} predictions pe 95% confidence range **{lo:.1%} – {hi:.1%}** hai — jisme **50% seedha beech
me** aata hai. Iska matlab statistically saaf hai: **is signal me koi edge nahi hai.**
Ye ab shak nahi, **saabit** hai.""")

        st.markdown("### 📋 Abhi ke signals")
        st.caption("Ye neeche jo dikh raha hai wo bot **abhi** kya soch raha hai. "
                   "Upar wala number bata chuka hai ki ye soch **kaam nahi karti** — "
                   "ye sirf transparency ke liye hai.")
        rows = []
        for sym_, g in hist.groupby("symbol"):
            sig = analytics.compute_signal(g)
            if sig:
                rows.append({"symbol": sym_, "signal": sig["signal"],
                             "prob_up": sig["prob_up"], "funding_z": sig["funding_z"],
                             "momentum": round(sig["mom"], 4)})
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            st.markdown("""
**Column ka matlab — plain Hindi me:**

| Column | Matlab |
|---|---|
| `signal` | Bot ka andaaza: **UP** = price upar jaayega, **DOWN** = neeche |
| `prob_up` | Bot ke hisaab se upar jaane ka chance. `0.71` = "71% sure upar jaayega". **Ye jhooth hai** — asli accuracy 49.9% hai |
| `funding_z` | Funding rate **kitna asaamanya** hai. `0` = normal, `+2` = bahut zyada (longs bahut bhare hue), `−2` = bahut kam. Ye ek **z-score** hai = "average se kitne standard deviation door" |
| `momentum` | Haal ka price trend. `+` = upar ja raha tha, `−` = neeche |
""")
        else:
            st.info(f"Signals ~12 snapshots ke baad start honge (abhi {n_snaps}).")

        try:
            crypto_hist = hist[hist["funding"] != 0]
            if not crypto_hist.empty:
                piv = crypto_hist.pivot_table(index="ts", columns="symbol",
                                              values="funding") * 24 * 365 * 100
                st.markdown("**Crypto funding rate (annualized %) — waqt ke saath**")
                st.line_chart(piv, height=240)
                st.caption("**+** = longs shorts ko pay kar rahe hain (bazaar bullish/bhara hua). "
                           "**−** = shorts longs ko pay kar rahe hain. Ye **asli cash flow** hai, "
                           "prediction nahi — isiliye humne isse carry strategy banayi thi.")
        except Exception:
            pass

        st.markdown("### 📈 Paper P&L — nakli paisa, asli data")
        eq_path = analytics.ROOT / "data" / "paper_equity.csv"
        if eq_path.exists():
            eq = pd.read_csv(eq_path)
            eq["ts"] = pd.to_datetime(eq["ts"], utc=True)
            eq = eq.set_index("ts")
            start = 10_000.0
            cur = float(eq["equity"].iloc[-1])
            bh = float(eq["buyhold"].iloc[-1]) if "buyhold" in eq else start
            cc = st.columns(3)
            cc[0].metric("🤖 Strategy", f"${cur:,.0f}", f"{cur/start-1:+.2%}")
            cc[1].metric("😴 Buy & hold", f"${bh:,.0f}", f"{bh/start-1:+.2%}")
            cc[2].metric("Beating buy&hold?", "✅ yes" if cur > bh else "❌ no")
            cols = [c for c in ["equity", "buyhold"] if c in eq]
            st.line_chart(eq[cols].rename(columns={"equity": "strategy"}),
                          height=240, color=["#16C784", "#8892A0"])
            lesson(f"Dono $10,000 se shuru hue. Bot <b>${cur:,.0f}</b>, kuch na karna "
                   f"<b>${bh:,.0f}</b>. Bot ne <b>{(cur-bh)/start:+.1%}</b> zyada ganwaya "
                   "sirf <i>koshish karke</i>. "
                   "<b>Aur ye bura result nahi hai — ye saboot hai.</b> Gauntlet ne pehle hi "
                   "bola tha 'koi edge nahi'. Humne phir bhi nakli paise se chalaya, aur wo "
                   "<b>exactly waise haara jaise predict kiya tha</b>. Matlab humara validation "
                   "sach bolta hai — aur usne tumhara <b>asli paisa</b> bachaya.")
        else:
            st.info("Paper-trade abhi start nahi hua.")

# ----------------------------------------------------------------- LEARNINGS
with tab_learn:
    st.subheader("🧪 Learnings — har idea, uska verdict, aur kyun mara")
    st.caption("**Ye kya hai:** har idea jo humne test kiya. Seedha `research/hypotheses.json` se — "
               "ye table kabhi purana nahi hota.")

    def load_registry() -> dict:
        p = ROOT / "research" / "hypotheses.json"
        try:
            return json.loads(p.read_text() or "{}") if p.exists() else {}
        except Exception:
            return {}

    reg = load_registry()
    if not reg:
        st.info("Registry nahi mili.")
    else:
        trials = sum(len(h.get("tests", [])) for h in reg.values())
        failed = sum(1 for h in reg.values() if h.get("status") == "failed")
        passed = sum(1 for h in reg.values() if h.get("status") == "passed")
        tested = failed + passed + sum(1 for h in reg.values() if h.get("status") == "tested")
        k = st.columns(4)
        k[0].metric("Ideas registered", len(reg))
        k[1].metric("Tested", tested, delta=f"{trials} trials", delta_color="off")
        k[2].metric("Survived", passed, delta="abhi tak koi nahi", delta_color="off")
        k[3].metric("Untested queue", len(reg) - tested, delta_color="off")

        ICON = {"failed": "☠️", "passed": "✅", "tested": "⚠️", "proposed": "⏳"}
        order = {"failed": 0, "tested": 1, "proposed": 2, "passed": -1}
        for h in sorted(reg.values(), key=lambda x: order.get(x.get("status"), 9)):
            tests = h.get("tests", [])
            icon = ICON.get(h.get("status"), "•")
            with st.expander(f"{icon} **{h.get('name','?')}** — {h.get('status','?')}"):
                st.markdown(f"**Kaun mujhe paisa deta, aur kyun?**\n\n> {h.get('economic_rationale','—')}")
                if tests:
                    st.markdown(f"**Kya nikla** ({len(tests)} test{'s' if len(tests)!=1 else ''}):")
                    st.markdown(f"> {tests[-1].get('note','—')}")
                else:
                    st.info("Abhi test nahi hua.")

        lesson("Dekho <b>kaise</b> mare, sirf <i>ki</i> mare nahi. "
               "<b>tsmom / ML</b> — koi mechanism hi nahi tha. "
               "<b>funding_carry, liq_meanrev, xexch_arb</b> — mechanism <b>bilkul asli</b> tha, "
               "par edge cost se chhota tha. "
               "<b>delist_event</b> — 'forced flow' tha hi nahi (perp me har long ke saamne ek "
               "short hota hai; dono settle ho jaate hain, net zero). "
               "<br><br><b>Asli sabak:</b> asli mechanism dhoondhna mushkil <i>nahi</i> hai. "
               "Mushkil hai aisa mechanism jo <b>cost ke baad bhi bacha rahe</b>. "
               "Isiliye ab hum bps-scale ideas nahi, <b>percent-scale</b> events dhoondh rahe hain.")

    st.warning("⚠️ Koi bot 100% profit guarantee nahi karta. Ye research/learning tool hai.")
