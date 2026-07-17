"""Append one market snapshot to daily CSV storage. Run on a schedule (24/7).

    python collector.py

Storage: data/market/YYYY-MM-DD.csv (one file per UTC day, appended each run).
Runs on GitHub Actions cron (free, no PC needed) or locally / on a VPS.
"""
from __future__ import annotations

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import datetime, timezone
from aitrader.collector import fetch_snapshot, FIELDS
from aitrader.collector import analytics
from aitrader.collector.snapshot import fetch_yahoo

CRYPTO = ["BTCUSDT", "ETHUSDT", "SOLUSDT", "XRPUSDT"]          # Kraken perps
YAHOO = {                                                      # our name -> Yahoo symbol
    "AAPL": "AAPL", "SPY": "SPY", "NASDAQ": "^IXIC",            # US equities
    "RELIANCE": "RELIANCE.NS", "NIFTY": "^NSEI", "SENSEX": "^BSESN",  # India
    "EURUSD": "EURUSD=X", "GOLD": "GC=F",                       # forex / commodity
}
STORE = Path(__file__).resolve().parent / "data" / "market"


def main() -> None:
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = fetch_snapshot(CRYPTO, ts) + fetch_yahoo(YAHOO, ts)   # crypto + all markets
    if not rows:
        print("No data fetched (sources unreachable). Nothing written.")
        return
    STORE.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    path = STORE / f"{day}.csv"
    new_file = not path.exists()
    with open(path, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {path.relative_to(STORE.parent.parent)}")
    for r in rows:
        print(f"  {r['symbol']:9} ${r['price']:>10,.2f}  funding {r['funding']*100:+.4f}%  "
              f"OI {r['open_interest']:,.0f}")

    # --- intelligence layer: compute signals, log predictions, score matured ones ---
    hist = analytics.load_history()
    logged = analytics.log_predictions(hist)
    if logged:
        print("Signals logged:", ", ".join(f"{r['symbol']}={r['signal']}" for r in logged))
    else:
        print("Signals: not enough history yet (builds over time).")
    score = analytics.score_predictions(hist)
    print("Forward accuracy:", score)

    # --- forward paper-trade with fake money (the real test) ---
    from aitrader.collector import paper
    pnl = paper.mark_and_trade(hist, analytics)
    print("Paper P&L (directional):", pnl)

    # --- delta-neutral funding carry (the REAL profit mechanism) ---
    from aitrader.collector import carry_paper
    carry = carry_paper.step(hist)
    print("Carry P&L (delta-neutral):", carry)

    # --- cross-exchange funding arbitrage (structural edge) — log spreads over time ---
    try:
        from aitrader.research.xexch_funding import fetch_cross_funding, XFUNDING_FIELDS
        xrows = fetch_cross_funding()
        if xrows:
            xpath = STORE.parent / "xfunding.csv"
            new = not xpath.exists()
            with open(xpath, "a", newline="") as f:
                w = csv.DictWriter(f, fieldnames=XFUNDING_FIELDS)
                if new:
                    w.writeheader()
                w.writerows(xrows)
            best = max(xrows, key=lambda r: r["spread_pct"])
            print(f"X-exch funding: best spread {best['coin']} {best['spread_pct']}% "
                  f"(long {best['long_on']} / short {best['short_on']})")
    except Exception as e:
        print("x-exch funding skipped:", str(e)[:60])

    # --- OKX funding-interval regime flag (FORCED_FLOW_MAP.md §2.1) ---
    # Diff-based: the signal is the CHANGE between polls and CANNOT be backfilled, so this
    # ships before any strategy is written. Every day not polled is lost permanently.
    try:
        from aitrader.collector import regime
        r = regime.step()
        if r.get("ok"):
            msg = (f"Regime (OKX): {r['symbols']} swaps | pinned@cap(live) "
                   f"{r['pinned_live_now']} | events {r['events']}")
            if r["escalations"]:
                msg += f" | ESCALATIONS {r['escalations']}"
            print(msg)
            if r["hot"]:
                print("  hot:", ", ".join(r["hot"]))
        else:
            print("Regime skipped:", r.get("reason"))
    except Exception as e:
        print("Regime skipped:", str(e)[:60])


if __name__ == "__main__":
    main()
