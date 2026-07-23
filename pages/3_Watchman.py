"""Watchman — the GO-SIGNAL page. One question, answered live: koi tradeable episode hai?

Why this page exists: the cloud routine's reports live on claude.ai/code, which needs its
own setup. The user asked for the same check inside OUR dashboard instead — better,
actually: this page checks LIVE every time it is opened, not on a 6-hour clock.

Everything here is either read from the repo's data files (the collector commits fresh
CSVs every ~10 min, and Streamlit Cloud redeploys on every push) or fetched live from
OKX public endpoints (no auth; OKX is reachable from Streamlit Cloud — verified, unlike
Bybit which geo-blocks US datacenter IPs).

THE ONE THING THIS PAGE WATCHES FOR (see research/hypotheses.json, funding_escalation):
a symbol whose funding is escalated/pinned AND whose base coin is BORROWABLE on OKX.
Every episode so far failed that second half: LRC (borrowable but delisted 3 days later),
LA / ONE / O (not borrowable at all). The day this page shows a GO SIGNAL is the day the
hypothesis finally gets its live test.
"""
from __future__ import annotations

import glob
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from aitrader.collector.regime import fetch_borrow, fetch_okx_regime  # noqa: E402

st.set_page_config(page_title="Watchman", page_icon="🛰️", layout="wide")

st.markdown("""
<style>
  .block-container{padding-top:2.2rem;}
  div[data-testid="stMetric"]{background:#161B22;border:1px solid #26303B;
     border-radius:14px;padding:.7rem 1rem;}
  .lesson{background:#0E1F2A;border:1px solid #2E8BFF55;border-left:4px solid #2E8BFF;
          border-radius:10px;padding:.85rem 1.1rem;margin:.8rem 0;}
  .lesson b{color:#6FB4FF;}
</style>
""", unsafe_allow_html=True)

st.title("🛰️ Watchman — GO-SIGNAL check")
st.caption("**Ye kya hai:** ek hi sawaal, live jawab — *koi escalated coin hai jo BORROW bhi ho sakta ho?* "
           "Wahi ek cheez hai jiska hum intezaar kar rahe hain. Page kholte hi fresh check hota hai.")


# ------------------------------------------------------------------ live fetches
@st.cache_data(ttl=120, show_spinner="OKX se live state la raha hoon…")
def live_state():
    """Regime + borrow, one shot. ttl=120s so refreshes don't hammer OKX."""
    return fetch_okx_regime(), fetch_borrow()


@st.cache_data(ttl=120, show_spinner=False)
def spot_price(base: str) -> float | None:
    try:
        req = urllib.request.Request(
            f"https://www.okx.com/api/v5/market/ticker?instId={base}-USDT",
            headers={"User-Agent": "aitrader/0.1"})
        d = json.loads(urllib.request.urlopen(req, timeout=10).read())
        return float(d["data"][0]["last"])
    except Exception:
        return None


if st.button("🔄 Refresh (fresh check abhi)"):
    st.cache_data.clear()

regime, borrow = live_state()

if not regime:
    st.error("OKX unreachable from this host — thodi der me refresh karo.")
    st.stop()

# ------------------------------------------------------------------ the verdict
# Escalated = interval unambiguously below the 4h/8h per-symbol defaults, OR pinned at cap.
flagged = {}
for inst, s in regime.items():
    if s["interval_h"] <= 2 or s.get("at_cap_live") or s.get("at_cap_sett"):
        flagged[inst] = s

go, blocked = [], []
for inst, s in flagged.items():
    base = inst.split("-")[0]
    b = borrow.get(base)
    (go if b else blocked).append((inst, base, s, b))

if go:
    st.success("## 🚨 GO SIGNAL — escalated AND borrowable coin mila!")
    for inst, base, s, b in go:
        px = spot_price(base)
        quota_usd = (b["quota"] * px) if px else None
        c = st.columns(4)
        c[0].metric("Symbol", inst)
        c[1].metric("Interval", f'{s["interval_h"]:g}h',
                    help="8h/4h = normal. 2h/1h = escalated (funding cap pe atka tha)")
        c[2].metric("Funding rate", f'{s["funding_rate"]*100:+.4f}%',
                    f'cap ±{s["cap"]*100:.3f}%', delta_color="off")
        c[3].metric("Borrow quota", f'${quota_usd:,.0f}' if quota_usd else f'{b["quota"]:,.0f} coins',
                    f'{b["rate"]*100:.4f}%/day borrow rate', delta_color="off")
    st.markdown('<div class="lesson">💡 <b>Ab kya karein:</b> Claude ko batao "GO SIGNAL aaya hai" — '
                'pehla kadam TRADE nahi hai. Pehla kadam: is episode ko live record karna '
                '(kitna funding accrue hota hai, borrow sach me milta hai ya nahi). '
                'Trade sirf gauntlet ke baad, chhote size me.</div>', unsafe_allow_html=True)
elif flagged:
    st.warning(f"## Episode chal raha hai — par tradeable NAHI (borrow nahi milta)")
    for inst, base, s, b in blocked:
        st.markdown(f"- **{inst}** — interval `{s['interval_h']:g}h`, "
                    f"funding `{s['funding_rate']*100:+.4f}%` (cap ±{s['cap']*100:.3f}%) — "
                    f"**{base} NOT BORROWABLE** → hedge impossible → trade nahi")
else:
    st.info("## Abhi koi escalated/pinned coin nahi — market normal hai")

# ------------------------------------------------------------------ interval distribution
from collections import Counter
dist = Counter()
for s in regime.values():
    h = s["interval_h"]
    dist[int(h) if float(h).is_integer() else h] += 1
c = st.columns(5)
c[0].metric("OKX swaps", len(regime))
c[1].metric("1h pe", dist.get(1, 0), help="escalated — funding cap pe atka tha")
c[2].metric("2h pe", dist.get(2, 0), help="escalated")
c[3].metric("4h pe", dist.get(4, 0), help="normal default (225+ symbols ka default 4h hai)")
c[4].metric("8h pe", dist.get(8, 0), help="normal default")

# ------------------------------------------------------------------ collector heartbeat
st.markdown("### 📡 Collector heartbeat")
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob(os.path.join(ROOT, "data", "market", "*.csv")))
if files:
    d = pd.read_csv(files[-1], parse_dates=["ts"])
    age = (pd.Timestamp.now(tz="UTC") - d.ts.max()).total_seconds() / 60
    ist = d.ts.max().tz_convert("Asia/Kolkata")
    if age < 45:
        st.success(f"🟢 Collector ALIVE — last snapshot {age:.0f} min pehle ({ist:%d-%b %I:%M %p} IST)")
    else:
        st.error(f"🔴 Collector ruka hua lagta hai — last snapshot {age:.0f} min pehle "
                 f"({ist:%d-%b %I:%M %p} IST). GitHub Actions check karo. "
                 f"(Note: ye deployed app repo ke saath update hoti hai — thoda lag normal hai.)")
else:
    st.warning("data/market/ me koi file nahi mili.")

# ------------------------------------------------------------------ recent events
st.markdown("### 📋 Pichhle 48 ghante ke events")
EXPLAIN = {
    "escalate": "🔺 interval chhota hua — funding cap pe atka tha, OKX ne wasooli tez ki",
    "de_escalate": "🔻 wapas normal — episode khatam",
    "pin_start": "📌 funding cap/floor pe atka",
    "pin_end": "📍 cap se hata",
    "cap_bind": "⚠️ settled rate cap pe laga (escalation ka trigger)",
    "cap_release": "✅ cap se release",
    "delisted": "☠️ coin DELIST ho gaya",
    "listed": "🆕 naya perp list hua",
}
ev_path = os.path.join(ROOT, "data", "regime", "okx_events.csv")
if os.path.exists(ev_path):
    e = pd.read_csv(ev_path, parse_dates=["ts"])
    recent = e[e.ts >= pd.Timestamp.now(tz="UTC") - pd.Timedelta(hours=48)].sort_values("ts", ascending=False)
    if len(recent):
        for _, r in recent.iterrows():
            ist = r.ts.tz_convert("Asia/Kolkata")
            st.markdown(f"- `{ist:%d-%b %I:%M %p}` **{r.inst_id}** — "
                        f"{EXPLAIN.get(r.event, r.event)} (`{r.old} → {r.new}`)")
    else:
        st.caption("48h me koi regime event nahi — shaant market.")
else:
    st.caption("events file abhi nahi bani.")

# ------------------------------------------------------------------ episode scoreboard
st.markdown("### 🧾 Ab tak ka scoreboard — har episode ka anjaam")
b_path = os.path.join(ROOT, "data", "regime", "okx_borrow.csv")
if os.path.exists(b_path):
    b = pd.read_csv(b_path, parse_dates=["ts"])
    esc = b[b.reason != "control"]
    delisted_insts = set()
    if os.path.exists(ev_path):
        delisted_insts = {i.split("-")[0] for i in e[e.event == "delisted"].inst_id}
    rows = []
    for ccy, g in esc.groupby("ccy"):
        borrowable = g.rate.notna().any()
        rows.append({
            "coin": ccy,
            "observations": len(g),
            "borrowable?": "✅ haan" if borrowable else "❌ nahi",
            "anjaam": ("☠️ delist ho gaya" if ccy in delisted_insts
                       else ("😤 hedge nahi ho sakta" if not borrowable else "👀 dekh rahe hain")),
        })
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        n_ok = sum(1 for r in rows if r["borrowable?"].startswith("✅") and "delist" not in r["anjaam"])
        st.markdown(f'<div class="lesson">💡 <b>Isse kya samajhna hai:</b> funding escalation '
                    f'<b>asli hai aur bar-bar hota hai</b> — system use pakad raha hai. Par ab tak '
                    f'<b>har episode untradeable nikla</b>: ya coin borrow nahi hota (hedge impossible), '
                    f'ya delist ho gaya. Abhi tradeable-and-alive: <b>{n_ok}</b>. '
                    f'Jis din upar GO SIGNAL dikhe — us din hypothesis ka asli live test shuru hota hai. '
                    f'Tab bhi pehla kadam trade nahi, <b>recording</b> hai.</div>',
                    unsafe_allow_html=True)
else:
    st.caption("borrow tracker abhi shuru hua hai.")

st.caption("Data: OKX public APIs (live, page kholte hi) + repo CSVs (collector har 10 min commit karta hai). "
           "Cloud watchman routine bhi har 6 ghante background me yahi check karti hai.")
