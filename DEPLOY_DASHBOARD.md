# Deploy the aitrader dashboard (see your architecture on your phone)

The dashboard (`dashboard.py`) shows the architecture diagram, a live agent decision,
and a net-of-cost backtest. Runs in mock mode — no API keys.

## Deploy free on Streamlit Community Cloud
1. Push this project to a GitHub repo (done for you → `gyanrnk/aitrader-bot`).
2. Go to **https://share.streamlit.io** → sign in with GitHub (**gyanrnk**).
3. **Create app** → select:
   - Repository: `gyanrnk/aitrader-bot`
   - Branch: `master`
   - **Main file path: `dashboard.py`**
4. **Deploy** → ~1–2 min → you get a public URL like
   `https://aitrader-bot-xxxx.streamlit.app`.
5. On your phone: open the URL → browser menu → **Add to Home screen**.

## Tabs
- 🏗️ **Architecture** — the full system as a live diagram
- 🧠 **Live Decision** — run one symbol, see analyst reports + Bull/Bear debate + risk debate
- 📊 **Backtest** — walk-forward, net-of-cost scorecard vs baselines
- 🧪 **What we learned** — the experiment results (meta vs funding)

Use `mock` data for instant/offline; `yfinance` for real data (may be slow/flaky on free tier).
