# Deploy the aitrader app (News + Bot Dashboard in ONE app)

Single Streamlit multi-page app: sidebar has **Trading News** and **Bot Dashboard**.
Runs in mock mode — no API keys.

## Deploy free on Streamlit Community Cloud
1. Repo is already on GitHub → `gyanrnk/aitrader-bot`.
2. Go to **https://share.streamlit.io** → sign in with GitHub (**gyanrnk**).
3. **Create app** → select:
   - Repository: `gyanrnk/aitrader-bot`
   - Branch: `master`
   - **Main file path: `Home.py`**   ← important (not dashboard.py)
4. **Deploy** → ~2 min → public URL like `https://aitrader-xxxx.streamlit.app`.
5. Phone: open URL → menu → **Add to Home screen**. Sidebar (top-left **›**) me do pages.

## Pages
- 📈 **Trading News** — free RSS news, filters, sentiment, "ideas for our bot"
- 🤖 **Bot Dashboard** — architecture diagram, live agent decision, net-of-cost backtest

## Local run
```bash
pip install -r requirements.txt
streamlit run Home.py
```
