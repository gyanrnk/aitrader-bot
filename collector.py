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
            gos = r.get("go_signals") or []
            if gos:
                print("GO SIGNAL:", ", ".join(f'{g["ccy"]} ({g["inst_id"]})' for g in gos))
                _go_signal_github_alert(gos)
        else:
            print("Regime skipped:", r.get("reason"))
    except Exception as e:
        print("Regime skipped:", str(e)[:60])


def _go_signal_github_alert(gos: list[dict]) -> None:
    """GO signal -> open a GitHub issue -> GitHub emails the repo owner. Zero setup.

    Why an issue and not email/telegram: the collector already runs inside GitHub
    Actions with a GITHUB_TOKEN, and GitHub notifies the owner about new issues in
    their own repo by default. No SMTP password, no bot token, nothing to configure.

    Dedupe matters: the collector fires every 10 minutes and an episode lasts hours
    (LRC stayed escalated for DAYS) — without dedupe one episode would send hundreds
    of emails. One OPEN issue per coin = one alert per episode; closing the issue
    re-arms the alert for that coin.
    """
    import json as _json
    import os as _os
    import urllib.request as _rq

    token, repo = _os.environ.get("GITHUB_TOKEN"), _os.environ.get("GITHUB_REPOSITORY")
    if not token or not repo:
        return                          # local run — the console line above is enough
    base = f"https://api.github.com/repos/{repo}/issues"
    hdrs = {"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json",
            "User-Agent": "aitrader-collector"}
    try:
        with _rq.urlopen(_rq.Request(base + "?state=open&per_page=100", headers=hdrs),
                         timeout=20) as resp:
            open_titles = " ".join(i.get("title", "") for i in _json.loads(resp.read()))
    except Exception as e:
        print("GO alert: could not list issues:", str(e)[:60])
        return
    for g in gos:
        if f"GO SIGNAL: {g['ccy']}" in open_titles:
            continue                    # already alerted for this episode
        body = (f"**Escalated AND borrowable — the condition every prior episode failed.**\n\n"
                f"| | |\n|---|---|\n"
                f"| Symbol | `{g['inst_id']}` |\n"
                f"| Interval | {g['interval_h']}h |\n"
                f"| Borrow quota | {g['quota']:,.0f} coins |\n"
                f"| Borrow rate | {(g['rate'] or 0) * 100:.4f}%/day |\n"
                f"| Detected (UTC) | {g['ts']} |\n\n"
                f"**Pehla kadam RECORDING hai, trade nahi** — dashboard ka Watchman page kholo, "
                f"phir Claude ko bolo. Trade sirf gauntlet ke baad.\n\n"
                f"_Issue close karne par is coin ke liye alert phir se armed ho jayega._")
        try:
            req = _rq.Request(base, method="POST", headers=hdrs, data=_json.dumps(
                {"title": f"🚨 GO SIGNAL: {g['ccy']} — escalated & borrowable",
                 "body": body}).encode())
            with _rq.urlopen(req, timeout=20) as resp:
                print(f"GO alert: issue created for {g['ccy']} (#"
                      f"{_json.loads(resp.read()).get('number')})")
        except Exception as e:
            print(f"GO alert: issue create failed for {g['ccy']}:", str(e)[:60])


if __name__ == "__main__":
    main()
