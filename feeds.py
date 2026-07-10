"""Free, keyless RSS news sources for trading. No API keys required anywhere.

Google News RSS entries are query-based and very reliable — used as robust fallbacks.
Add/remove sources freely; each is (name, url, category).
"""

FEEDS = [
    # ---------- Crypto ----------
    ("CoinDesk", "https://www.coindesk.com/arc/outboundfeeds/rss/", "Crypto"),
    ("Cointelegraph", "https://cointelegraph.com/rss", "Crypto"),
    ("Decrypt", "https://decrypt.co/feed", "Crypto"),
    ("CryptoSlate", "https://cryptoslate.com/feed/", "Crypto"),
    ("Google News · Bitcoin",
     "https://news.google.com/rss/search?q=bitcoin+OR+ethereum+crypto&hl=en-US&gl=US&ceid=US:en",
     "Crypto"),

    # ---------- Global markets ----------
    ("MarketWatch", "http://feeds.marketwatch.com/marketwatch/topstories/", "Global"),
    ("Investing.com", "https://www.investing.com/rss/news.rss", "Global"),
    ("CNBC Markets",
     "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=20910258",
     "Global"),
    ("Google News · Stock Market",
     "https://news.google.com/rss/search?q=stock+market+when:1d&hl=en-US&gl=US&ceid=US:en",
     "Global"),

    # ---------- India ----------
    ("ET Markets",
     "https://economictimes.indiatimes.com/markets/rssfeeds/1977021501.cms", "India"),
    ("Moneycontrol", "https://www.moneycontrol.com/rss/latestnews.xml", "India"),
    ("Livemint Markets", "https://www.livemint.com/rss/markets", "India"),
    ("Google News · Nifty/Sensex",
     "https://news.google.com/rss/search?q=nifty+OR+sensex+OR+nse+when:1d&hl=en-IN&gl=IN&ceid=IN:en",
     "India"),
]

CATEGORIES = ["Crypto", "Global", "India"]

BULL_WORDS = {"surge", "soar", "rally", "gain", "jump", "high", "bullish", "rise",
              "boost", "record", "up", "top", "beat", "upgrade", "inflow", "adopt"}
BEAR_WORDS = {"crash", "plunge", "fall", "drop", "slump", "bearish", "loss", "down",
              "sink", "fear", "hack", "ban", "sell-off", "selloff", "warning", "cut",
              "outflow", "lawsuit", "fraud", "dump"}

BOT_THEMES = {
    "funding rate": "Ties to our funding-rate alt-data feature — watch for extremes.",
    "etf": "Flows/ETF news move crypto — candidate as a new data feature.",
    "rate": "Interest-rate news = macro regime signal for the regime layer.",
    "hack": "Risk event — the kind of tail our risk caps must survive.",
    "regulation": "Regime shifter; can invalidate a backtested edge.",
    "liquidation": "Positioning stress — related to funding/leverage signals.",
}
