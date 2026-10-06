"""aitrader — command center. Mobile-first landing page: ek nazar me faisla.

One question, answered at the top before anything else: *abhi trade hai ya nahi?* The old
Home was a research scorecard (what we tried, what died) — still true and still here, but
pushed into an expander. Now that the first real GO has fired, the page a phone opens to
should lead with the live decision, not the history.

EVERY number is read from disk / computed live — never hardcoded. Carry verdict comes from
aitrader.research.delta_carry on the committed funding history (same engine as the Watchman
page and the CLI), so Home, Watchman and `scripts/delta_carry_check.py` always agree.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from aitrader.research import delta_carry as dc  # noqa: E402

st.set_page_config(page_title="aitrader — command center", page_icon="🤖",
                   layout="centered", initial_sidebar_state="collapsed")

st.markdown("""
<style>
  .block-container{padding-top:2rem; padding-bottom:3rem; max-width:720px;}
  h1{margin-bottom:.1rem;}
  div[data-testid="stMetric"]{background:rgba(128,128,128,.06);
     border:1px solid rgba(128,128,128,.22); border-radius:12px; padding:.55rem .8rem;}
  .q{font-size:1.5rem; font-weight:700; margin:.6rem 0 .2rem;}
</style>
""", unsafe_allow_html=True)

st.title("🤖 aitrader")
st.caption("Command center — ek nazar me: **abhi trade hai ya nahi**, aur machine zinda hai ya nahi.")


# ---------------------------------------------------------------- live carry read
@st.cache_data(ttl=120, show_spinner=False)
def carry():
    rows = dc.load(ROOT / "data" / "delta" / "delta_funding.csv")
    if not rows:
        return None, None, None
    sym = dc.hottest(rows)
    if not sym:
        return rows, None, None
    return rows, sym, dc.analyze(rows, sym)


if st.button("🔄 Refresh"):
    st.cache_data.clear()

rows, sym, res = carry()

# ---------------------------------------------------------------- HERO: the one answer
st.markdown('<div class="q">Abhi trade hai?</div>', unsafe_allow_html=True)

# verdict code -> (banner fn, headline, plain-Hinglish gloss)
VERDICT_UI = {
    "CANDIDATE": (st.success, "🟢 CANDIDATE — setup ban raha hai",
                  "Short hold pe cost clear ho raha hai. **Claude ko bolo** → napkin R8 + "
                  "gauntlet → phir tiny trade. (Abhi bhi: pehle check, phir trade.)"),
    "THIN": (st.warning, "🟠 THIN — funding hai, par abhi patla",
             "Cost sirf lambe hold pe clear hota hai. Abhi ghusna = patla margin, risk zyada. "
             "**Watch** — tika toh CANDIDATE banega."),
    "WATCH": (st.warning, "🟡 WATCH — net positive par borderline",
              "Thoda aur richness/hold-time chahiye. Abhi kuch nahi."),
    "BELOW": (st.info, "⚪ Koi mauka nahi — market normal",
              "Koi hold window cost clear nahi karta. Machine watch kar rahi hai; GO pe email aayegi."),
    "FLIP": (st.info, "⚪ Funding ulta (negative) — skip",
             "Is direction me clean hedge nahi banta. Abhi kuch nahi."),
}

if res and res.get("ok"):
    code = res["verdict"]["code"]
    fn, head, gloss = VERDICT_UI.get(code, (st.info, code, res["verdict"]["msg"]))
    fn(f"### {head}\n\n{gloss}")

    go_live = res["latest_annual"] >= res["go_bar_annual"]
    w = {x["days"]: x for x in res["windows"]}
    c1, c2, c3 = st.columns(3)
    c1.metric(f"{res['symbol']} funding abhi", f"{res['latest_annual']:+.1f}%/yr",
              "🚨 50% paar" if go_live else "baseline", delta_color="off")
    if 3 in w:
        c2.metric("3-din hold: net", f"{w[3]['net']:+.2f}%",
                  f"{w[3]['apr']:.0f}%/yr", delta_color="off",
                  help="Agar 3 din hold karte: cumulative funding minus 0.40% round-trip cost")
    if 7 in w:
        c3.metric("7-din hold: net", f"{w[7]['net']:+.2f}%",
                  f"{w[7]['apr']:.0f}%/yr", delta_color="off")

    if go_live and code != "CANDIDATE":
        st.caption("🚨 **GO alert fire ho chuka** (funding ne 50% paar kiya — email gayi hogi). "
                   "Par carry abhi **cost clear nahi** kar raha, isliye verdict upar wala hai. "
                   "GO = *'dekho'*, trade nahi. Cost clear hote hi yahan 🟢 CANDIDATE dikhega.")
else:
    st.info("Delta funding data abhi load ho raha hai — thodi der me refresh karo.")

# ---------------------------------------------------------------- machine health
st.markdown("### 📡 Machine health")
files = sorted((ROOT / "data" / "market").glob("*.csv"))
hc1, hc2 = st.columns(2)
if files:
    try:
        d = pd.read_csv(files[-1], parse_dates=["ts"])
        age = (pd.Timestamp.now(tz="UTC") - d.ts.max()).total_seconds() / 60
        ist = d.ts.max().tz_convert("Asia/Kolkata")
        if age < 45:
            hc1.metric("Collector", "🟢 ALIVE", f"{age:.0f} min pehle", delta_color="off")
        else:
            hc1.metric("Collector", "🔴 ruka?", f"{age:.0f} min pehle", delta_color="off")
        hc2.metric("Aakhri data", f"{ist:%d-%b %H:%M}", "IST", delta_color="off")
    except Exception:
        hc1.caption("Heartbeat padhne me dikkat.")
else:
    hc1.caption("Market data file abhi nahi mili.")
st.caption("Data deployed app repo ke saath update hoti hai (collector har ~10 min commit karta hai) — "
           "thoda lag normal hai.")

# ---------------------------------------------------------------- carry detail
if res and res.get("ok"):
    st.markdown(f"### 📈 {res['symbol']} carry — funding TIKTA hai kya?")
    st.caption(f"{res['history_days']} din history · {res['n_settlements_total']} settlements · "
               f"round-trip cost {res['breakeven_cost_pct']:.2f}% · GO bar {res['go_bar_annual']:.0f}%/yr")

    tbl = pd.DataFrame([{
        "hold": f'{x["days"]}d', "setts": x["n"],
        "net-cost": f'{x["net"]:+.2f}%',
        "APR": f'{x["apr"]:.0f}%/yr',
        "≥bar": f'{x["above"]}/{x["n"]}',
    } for x in res["windows"]])
    st.dataframe(tbl, use_container_width=True, hide_index=True)

    setts = dc.settlements(rows, res["symbol"])[-12:]
    if setts:
        # s["dt"] is a stdlib datetime (UTC), not a pandas Timestamp, so it has no
        # tz_convert — shift by the fixed IST offset (+5:30, no DST) for the display label.
        chart = pd.DataFrame({
            "funding %/yr": [s["annual"] for s in setts],
            "GO bar (50)": [res["go_bar_annual"]] * len(setts),
        }, index=[(s["dt"] + pd.Timedelta(hours=5, minutes=30)).strftime("%d-%b %H:%M")
                  for s in setts])
        st.line_chart(chart, height=220)
    st.caption("net after cost = poora window hold karne pe cumulative funding − 0.40% round trip. "
               "Line GO bar ke upar + net positive = tabhi asli mauka.")

# ---------------------------------------------------------------- full scan: all hedgeable coins
st.markdown("### 🔭 Saare hedgeable coins — full scan")
st.caption("Delta pe **spot sirf 4 coins** ka hai (BTC/ETH/SOL/XRP) — baaki 222 perps hedge "
           "nahi ho sakte. Ye **poori tradeable list** hai, best-opportunity upar. (Delta naya "
           "spot coin add kare toh yahan khud aa jayega — code change nahi.)")
if rows:
    VMAP = {"CANDIDATE": "🟢 CANDIDATE", "WATCH": "🟡 WATCH", "THIN": "🟠 THIN",
            "BELOW": "⚪ BELOW", "FLIP": "⚪ FLIP"}
    scan_tbl = pd.DataFrame([{
        "coin": r["symbol"],
        "funding abhi": f'{r["latest_annual"]:+.0f}%/yr',
        "verdict": VMAP.get(r["verdict"]["code"], r["verdict"]["code"]),
        "best net": f'{max((w["net"] for w in r["windows"]), default=0):+.2f}%',
    } for r in dc.scan(rows)])
    st.dataframe(scan_tbl, use_container_width=True, hide_index=True)
    st.caption("Zyada coins = zyada GO — par sirf tab jab Delta zyada spot list kare. Abhi "
               "ceiling **4** hai. (Aur raasta: options-se-hedge — alag mechanism, baad me research.)")

# ---------------------------------------------------------------- what to do now
st.markdown("### 🎯 Abhi kya karna hai")
code = res["verdict"]["code"] if (res and res.get("ok")) else None
if code == "CANDIDATE":
    st.success("1️⃣ Claude ko bolo *'CANDIDATE aaya'* → **2️⃣** main napkin R8 + gauntlet chalaunga → "
               "**3️⃣** paas hua toh exact entry steps dunga → **4️⃣** tu Delta app pe **tiny** size se "
               "execute karega. Trade tera haath, tera paisa.")
else:
    st.info("Abhi **kuch nahi karna.** Machine watch kar rahi hai. Jis din 🟢 CANDIDATE dikhe "
            "(ya email aaye), tab Claude ko batana — pehla kadam napkin hai, trade nahi.")

# ---------------------------------------------------------------- the plan
with st.expander("🗺️ Poora plan — GO se asli trade tak (Phase 0–5)"):
    st.markdown("""
**Phase 0 — Abhi:** GO aaya, funding chadh raha. Carry THIN/cusp pe → sirf **watch**.

**Phase 1 — Account ready (tera kaam):** Delta India account (KYC), thoda **risk-capital jo kho
ke farak na pade**. Samajh lo: spot XRP **BUY**, perp **SHORT**, margin kahan, fees kitni.
**Zero rupee tab tak kharch nahi jab tak tu khud fund + trade na kare.**

**Phase 2 — CANDIDATE confirm (machine + Claude):** carry 🟢 CANDIDATE → napkin R8 (venue ✓,
dono legs ✓, edge > 2× cost) → gauntlet (cost-stress, persistence, falsification).

**Phase 3 — Pehla TINY trade (tera haath):** sabse chhoti size. Maqsad profit nahi — **plumbing
test:** funding sach me aata hai? hedge neutral rehta hai? asli slippage/fees? margin tikti hai?

**Phase 4 — Reconcile:** asli result vs model. Match → edge asli. Kam → asli cost pata chali.

**Phase 5 — Scale (sirf proven pe):** dheere size badhao, all-in kabhi nahi. Quarter-Kelly +
liquidity gated. Har GO pe repeat → track record.

**Honest expectation:** chhota, low-risk delta-neutral carry (~0.5%/hafta notional jab GO live,
*agar* tika). Side income, wealth-engine nahi. Value = machine batati hai **kab** act karna hai.
    """)

# ---------------------------------------------------------------- research scorecard (compact)
def load_registry() -> dict:
    p = ROOT / "research" / "hypotheses.json"
    try:
        return json.loads(p.read_text() or "{}") if p.exists() else {}
    except Exception:
        return {}


reg = load_registry()
if reg:
    tested = sum(1 for h in reg.values() if h.get("status") in ("tested", "failed", "passed"))
    passed = sum(1 for h in reg.values() if h.get("status") == "passed")
    trials = sum(len(h.get("tests", [])) for h in reg.values())
    with st.expander(f"🔬 Research scorecard — {tested} ideas test, {passed} bache ({trials} trials)"):
        st.caption("Seedha `research/hypotheses.json` se — kabhi stale nahi hota.")
        STATUS = {"failed": "☠️ REJECTED", "passed": "✅ PASSED",
                  "tested": "⚠️ tested, fragile", "proposed": "⏳ untested"}
        order = {"failed": 0, "tested": 1, "proposed": 2, "passed": -1}
        for h in sorted(reg.values(), key=lambda x: order.get(x.get("status"), 9)):
            st.markdown(f"**{h.get('name','?')}** — {STATUS.get(h.get('status'), h.get('status','?'))}  "
                        f"· family `{h.get('family','?')}` · {len(h.get('tests', []))} test(s)")
        st.caption("Har idea jo yahan mara, asli paise se marne se pehle mara. Yehi machine ka kaam hai.")

# ---------------------------------------------------------------- nav + footer
st.markdown("### 🧭 Aur dekho")
n0, n1 = st.columns(2)
n0.page_link("pages/3_Watchman.py", label="Watchman — GO-signal + carry (detail)",
             icon="🛰️", use_container_width=True)
n1.page_link("pages/2_Bot_Dashboard.py", label="Bot Dashboard — charts, gauntlet",
             icon="🤖", use_container_width=True)

st.caption("⚠️ Ye **monitor/decide** dashboard hai — trade yahan se **nahi** hota. Asli trade Delta "
           "India app pe, tere account se, tere haath se, gauntlet ke baad. Koi profit guarantee nahi.")
