"""Page 1 — Trading news aggregator (free RSS, no keys)."""
from __future__ import annotations

import html
import re
from datetime import datetime, timezone

import feedparser
import streamlit as st

from feeds import FEEDS, CATEGORIES, BULL_WORDS, BEAR_WORDS, BOT_THEMES

st.set_page_config(page_title="Trading News", page_icon="📈", layout="centered")

TAG_RE = re.compile(r"<[^>]+>")


def clean(text: str, limit: int = 240) -> str:
    text = html.unescape(TAG_RE.sub("", text or "")).strip()
    return text[:limit] + ("…" if len(text) > limit else "")


def sentiment(title: str) -> str:
    t = title.lower()
    b = sum(w in t for w in BULL_WORDS)
    s = sum(w in t for w in BEAR_WORDS)
    return "🟢" if b > s else "🔴" if s > b else "⚪"


def when(entry) -> datetime:
    for key in ("published_parsed", "updated_parsed"):
        tm = entry.get(key)
        if tm:
            return datetime(*tm[:6], tzinfo=timezone.utc)
    return datetime(1970, 1, 1, tzinfo=timezone.utc)


def ago(dt: datetime) -> str:
    if dt.year == 1970:
        return ""
    secs = (datetime.now(timezone.utc) - dt).total_seconds()
    if secs < 3600:
        return f"{int(secs // 60)}m ago"
    if secs < 86400:
        return f"{int(secs // 3600)}h ago"
    return f"{int(secs // 86400)}d ago"


@st.cache_data(ttl=600, show_spinner=False)
def fetch(selected_cats: tuple[str, ...]) -> list[dict]:
    items: list[dict] = []
    for name, url, cat in FEEDS:
        if cat not in selected_cats:
            continue
        try:
            parsed = feedparser.parse(url)
            for e in parsed.entries[:20]:
                title = clean(e.get("title", ""), 200)
                if not title:
                    continue
                items.append({
                    "title": title, "link": e.get("link", "#"),
                    "summary": clean(e.get("summary", ""), 220),
                    "source": name, "cat": cat, "dt": when(e),
                    "senti": sentiment(title),
                })
        except Exception:
            continue
    items.sort(key=lambda x: x["dt"], reverse=True)
    return items


st.title("📈 Trading News")
st.caption("Live trading & crypto news — free sources, no keys.")

with st.sidebar:
    st.header("Filters")
    cats = st.multiselect("Categories", CATEGORIES, default=CATEGORIES)
    query = st.text_input("Search keyword", "").strip().lower()
    max_items = st.slider("How many items", 10, 100, 40, step=10)
    if st.button("🔄 Refresh now"):
        fetch.clear()

if not cats:
    st.info("Pick at least one category.")
    st.stop()

with st.spinner("Fetching latest headlines…"):
    news = fetch(tuple(cats))

if query:
    news = [n for n in news if query in n["title"].lower() or query in n["summary"].lower()]

themes_hit = {}
for n in news:
    blob = (n["title"] + " " + n["summary"]).lower()
    for kw, note in BOT_THEMES.items():
        if kw in blob:
            themes_hit.setdefault(kw, note)
if themes_hit:
    with st.expander(f"💡 Ideas to watch for our bot ({len(themes_hit)})"):
        for kw, note in themes_hit.items():
            st.markdown(f"**{kw}** — {note}")

st.write(f"**{min(len(news), max_items)}** headlines")
for n in news[:max_items]:
    with st.container(border=True):
        st.markdown(f"### {n['senti']} [{n['title']}]({n['link']})")
        meta = f"`{n['cat']}` · **{n['source']}**"
        if ago(n["dt"]):
            meta += f" · {ago(n['dt'])}"
        st.caption(meta)
        if n["summary"]:
            st.write(n["summary"])

if not news:
    st.warning("No headlines matched. Clear the search or pick more categories.")

st.markdown("---")
st.caption("⚠️ News only — not financial advice.")
