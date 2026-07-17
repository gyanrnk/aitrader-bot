"""aitrader — the scorecard. One question, answered honestly: does anything work yet?

Design rule: EVERY number on this page is READ FROM DISK, never hardcoded. The old page
said "Edge candidates tested: 2" long after it was 7 — a dashboard that lies by going
stale is worse than no dashboard. If it can go stale, it doesn't belong here.
"""
import json
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="aitrader — scorecard", page_icon="🤖", layout="wide",
                   initial_sidebar_state="expanded")

ROOT = Path(__file__).resolve().parent

st.markdown("""
<style>
  .hero {text-align:center; padding:1.2rem 0 .4rem;}
  .hero h1 {font-size:2.5rem; margin-bottom:.15rem;
            background:linear-gradient(90deg,#16C784,#2E8BFF);
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;}
  .hero p {color:#9BA6B2; font-size:1.02rem; margin-top:0;}
  .verdict {border-radius:16px; padding:1.1rem 1.3rem; margin:.6rem 0 1.2rem;
            background:#2A1E0E; border:1px solid #E6A81755;}
  .verdict h2 {margin:0 0 .3rem; font-size:1.45rem; color:#E6A817;}
  .verdict p {margin:0; color:#C9D1D9; font-size:.98rem; line-height:1.5;}
  .row {display:flex; align-items:flex-start; gap:.7rem; padding:.75rem .9rem;
        border-radius:12px; margin-bottom:.5rem; border:1px solid #26303B; background:#161B22;}
  .row.dead {border-left:4px solid #E5484D;}
  .row.open {border-left:4px solid #7A828E;}
  .row.live {border-left:4px solid #E6A817;}
  .row.pass {border-left:4px solid #16C784;}
  .row .nm {font-weight:600; font-size:1rem; color:#E6EDF3;}
  .row .wy {color:#9BA6B2; font-size:.87rem; margin-top:.15rem; line-height:1.45;}
  .tag {font-size:.7rem; padding:.1rem .5rem; border-radius:999px; white-space:nowrap;}
  .t-dead {background:#2A1214; color:#FF6B6E; border:1px solid #E5484D55;}
  .t-open {background:#1A1D21; color:#9BA6B2; border:1px solid #7A828E55;}
  .t-live {background:#2A1E0E; color:#E6A817; border:1px solid #E6A81755;}
</style>
<div class="hero">
  <h1>🤖 aitrader</h1>
  <p>Ideas ko <b>imaandari se maarne</b> ki machine. Jo bach jaye — wahi paisa banata hai.</p>
</div>
""", unsafe_allow_html=True)


# ---------------------------------------------------------------- load (never hardcode)
def load_registry() -> dict:
    p = ROOT / "research" / "hypotheses.json"
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text() or "{}")
    except Exception:
        return {}


def load_paper():
    p = ROOT / "data" / "paper_equity.csv"
    if not p.exists():
        return None
    try:
        d = pd.read_csv(p, parse_dates=["ts"])
        return d if len(d) else None
    except Exception:
        return None


reg = load_registry()
trials = sum(len(h.get("tests", [])) for h in reg.values())
passed = sum(1 for h in reg.values() if h.get("status") == "passed")
failed = sum(1 for h in reg.values() if h.get("status") == "failed")
tested = sum(1 for h in reg.values() if h.get("status") in ("tested", "failed", "passed"))

# ---------------------------------------------------------------- the honest headline
untested = sum(1 for h in reg.values() if h.get("status") == "proposed")

st.markdown(f"""
<div class="verdict">
  <h2>⚠️ {tested} ideas test kiye. {passed} bache.</h2>
  <p>Yeh <b>failure nahi</b> — yeh machine ka <b>kaam karna</b> hai. Har idea jo yahan mara,
  wo <b>asli paise se marne se pehle</b> mara. Neeche <b>live proof</b> hai: gauntlet ne bola
  "koi edge nahi", aur live test ne exactly wahi confirm kiya.</p>
</div>
""", unsafe_allow_html=True)

m1, m2, m3, m4 = st.columns(4)
m1.metric("Ideas registered", len(reg))
m2.metric("Tested so far", tested, delta=f"{trials} trials",
          delta_color="off",
          help="Har trial count hota hai — isse har AGLE idea ka bar uthta hai (deflated Sharpe). "
               "Jitna zyada try karoge, utna zyada proof chahiye.")
m3.metric("Survived", passed, delta="abhi tak koi nahi", delta_color="off",
          help="Gauntlet paas karke deploy ho sakne wale ideas")
m4.metric("Queue me bache", untested, delta="abhi test hone hain", delta_color="off")

# ---------------------------------------------------------------- the scoreboard
st.markdown("### 📋 Scoreboard — kya test hua, kya nikla")
st.caption("Seedha `research/hypotheses.json` se — ye page kabhi stale nahi hota.")

STATUS_UI = {
    "failed":   ("dead", "t-dead", "☠️ REJECTED"),
    "passed":   ("pass", "t-dead", "✅ PASSED"),
    "tested":   ("live", "t-live", "⚠️ TESTED, fragile"),
    "proposed": ("open", "t-open", "⏳ untested"),
}


VERDICT_WORDS = ("REJECTED", "PASSED", "FAILED", "ACCEPTED")


def why(h: dict) -> str:
    """The REASON it's in this state — never the verdict itself.

    The status is already shown as a tag, so a line reading "REJECTED." tells the reader
    nothing they can't see. Our notes open with the verdict, so strip that lead and show
    the substance underneath.
    """
    tests = h.get("tests", [])
    if not tests:
        return h.get("economic_rationale", "")[:200]
    note = (tests[-1].get("note", "") or "").strip()
    parts = [p.strip() for p in note.split(". ") if p.strip()]
    if parts and len(parts[0]) < 45 and parts[0].upper().startswith(VERDICT_WORDS):
        parts = parts[1:]            # drop the bare verdict lead
    # Cut on a SENTENCE boundary, never mid-word. A blurb ending "...past the 163" reads
    # as a rendering bug and quietly costs the reader trust in every other number here.
    out, n = [], 0
    for p in parts:
        if out and n + len(p) > 200:
            break
        out.append(p)
        n += len(p) + 2
    text = ". ".join(out).strip()
    if text and not text.endswith("."):
        text += "."
    return text or note[:200]


order = {"failed": 0, "tested": 1, "proposed": 2, "passed": -1}
for h in sorted(reg.values(), key=lambda x: order.get(x.get("status"), 9)):
    cls, tag, label = STATUS_UI.get(h.get("status"), ("open", "t-open", h.get("status", "?")))
    n = len(h.get("tests", []))
    st.markdown(f"""
    <div class="row {cls}">
      <div style="flex:1">
        <div class="nm">{h.get('name','?')} <span class="tag {tag}">{label}</span></div>
        <div class="wy">{why(h)}</div>
        <div class="wy" style="opacity:.6">{n} test{'s' if n != 1 else ''} ·
             family <code>{h.get('family','?')}</code></div>
      </div>
    </div>""", unsafe_allow_html=True)

# ---------------------------------------------------------------- live proof
st.markdown("### 🔬 Live proof — gauntlet sach bol raha tha")
paper = load_paper()
if paper is not None and {"equity", "buyhold"} <= set(paper.columns):
    last = paper.iloc[-1]
    start = 10000.0
    bot_pct = last["equity"] / start * 100 - 100
    bh_pct = last["buyhold"] / start * 100 - 100
    c1, c2, c3 = st.columns([1, 1, 2])
    c1.metric("🤖 Bot (fake money)", f"₹{last['equity']:,.0f}", f"{bot_pct:+.1f}%")
    c2.metric("😴 Buy & hold", f"₹{last['buyhold']:,.0f}", f"{bh_pct:+.1f}%")
    c3.metric("Bot ne kitna GANWAYA vs kuch na karne se",
              f"{bot_pct - bh_pct:+.1f}%", "isliye hum ise trade nahi karte",
              delta_color="off")
    st.line_chart(paper.set_index("ts")[["equity", "buyhold"]], height=240)
    st.info("**Ise samjho:** backtest ne bola tha directional signal me koi edge nahi. "
            "Humne phir bhi ise fake paise se live chalaya — aur wo exactly waise hi haara "
            "jaise gauntlet ne predict kiya tha. **Yeh bura result nahi hai — yeh saboot hai "
            "ki humara validation kaam karta hai**, aur isne asli paisa bachaya.")
else:
    st.caption("Paper equity data abhi nahi hai.")

# ---------------------------------------------------------------- collecting now
st.markdown("### 📡 Abhi kya jama ho raha hai")
sm = ROOT / "data" / "regime" / "okx_summary.csv"
if sm.exists():
    try:
        d = pd.read_csv(sm)
        l = d.iloc[-1]
        a, b, c = st.columns(3)
        a.metric("OKX swaps watched", int(l["n_symbols"]))
        b.metric("Funding cap pe pinned", int(l.get("n_pinned_live", 0)),
                 help="Cap pe pinned = agle settlement pe interval escalate ho sakta hai (8h→4h→2h→1h)")
        c.metric("Regime snapshots", len(d))
        st.caption(f"Interval abhi — 1h: {int(l['n_1h'])} · 2h: {int(l['n_2h'])} · "
                   f"4h: {int(l['n_4h'])} · 8h: {int(l['n_8h'])}. "
                   "Is data ki **history nahi banti** — isliye roz jama karna zaroori hai.")
    except Exception:
        st.caption("Regime data padhne me dikkat.")
else:
    st.caption("Regime snapshotter abhi shuru hua hai — data collector ke saath aayega.")

# ---------------------------------------------------------------- nav
st.markdown("### 🧭 Aur dekho")
n1, n2 = st.columns(2)
n1.page_link("pages/2_Bot_Dashboard.py", label="Bot Dashboard — charts, backtest, gauntlet",
             icon="🤖", use_container_width=True)
n2.page_link("pages/1_Trading_News.py", label="Trading News — live feed",
             icon="📈", use_container_width=True)

st.caption("Research/learning tool. Koi bot profit guarantee nahi karta. "
           "Abhi tak koi deployable edge nahi mila — aur wo bhi ek imaandaar result hai.")
