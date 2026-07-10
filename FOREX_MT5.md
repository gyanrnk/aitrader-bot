# Forex / CFD via MetaTrader 5 (MT5)

Optional. Adds forex/CFD (and some brokers' crypto-CFD) **data + execution** to aitrader,
behind the same interfaces as the crypto providers. **Windows-only, local** — it needs the
MT5 desktop terminal running; it will NOT work on Streamlit Cloud.

## Honest notes first
- In forex/CFD you trade against the **broker's price feed** (spreads + overnight swaps),
  not a central exchange.
- There is **no funding-carry edge** here — that is crypto-specific. MT5 is for the
  momentum/mean-reversion style research (which must still pass the validation gauntlet).
- Always use a **DEMO account** first. Live orders are double-gated.

## Setup (one time, ~10 min)
1. Install the **MetaTrader 5 terminal** (from your broker or metaquotes.net).
2. Open a **free demo account** in the terminal (any broker) and log in.
3. In the terminal, add the symbols you want to Market Watch (e.g. EURUSD, XAUUSD).
4. Install the Python bridge:
   ```bash
   pip install MetaTrader5
   ```
5. (Optional) set login in `.env` so aitrader can initialize the terminal:
   ```
   MT5_LOGIN=12345678
   MT5_PASSWORD=your-demo-password
   MT5_SERVER=YourBroker-Demo
   AITRADER_MT5_TIMEFRAME=D1        # D1 | H4 | H1 | M15
   ```
   (If the terminal is already logged in, you can leave these blank.)

## Use
```python
from aitrader.config import Settings
from aitrader.data import get_provider

s = Settings(data_provider="mt5", mt5_timeframe="D1")
df = get_provider(s).ohlcv("EURUSD", lookback=400)   # normalized OHLCV
```
Backtest a forex symbol the same way as crypto:
```bash
AITRADER_DATA_PROVIDER=mt5 python scripts/backtest.py EURUSD
```
Execution (DEMO): set `AITRADER_BROKER=mt5` and `AITRADER_ALLOW_LIVE_ORDERS=yes`
only after you've reviewed lot-sizing in `aitrader/execution/mt5_broker.py`.

## Where it plugs in
- Data:      `aitrader/data/mt5_provider.py`  (get_provider → "mt5")
- Execution: `aitrader/execution/mt5_broker.py` (get_broker → "mt5", safety-gated)
Everything else (features, agents, backtest, gauntlet) works unchanged.
