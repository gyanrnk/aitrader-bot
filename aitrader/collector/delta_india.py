"""Delta Exchange India funding watcher — the machine, pointed at a venue we CAN trade.

WHY THIS EXISTS. OKX gave us a measured edge (funding_escalation, +1.6163% on BARD) that
we cannot execute — okx.com is blocked in India (MeitY / IT Act 2000). The obvious next
move is "find the same edge on a reachable venue." We checked, and the honest finding is:

  1. The ESCALATION MECHANISM is OKX-specific. Delta India funds at a FIXED 8h interval
     with no interval-escalation field — the 8h->4h->2h->1h rule simply does not exist
     here. So there is no drop-in alternate for that specific edge.

  2. The hedgeable set is tiny and quiet. Delta lists SPOT for only BTC/ETH/SOL/XRP, so
     a delta-neutral (short perp + buy spot, NO borrow) trade is only possible on those
     four. And those four are majors — their funding sits at the ~0.01%/8h baseline
     almost always. The extreme funding lives on microcaps (LAB +0.28%) that have no
     spot to hedge. This is exactly why `funding_carry` died: the coins we can hedge pay
     baseline, and the coins that pay well cannot be hedged.

So this is NOT a claim that Delta has an edge. It does not, today. What it IS: the watch
apparatus pointed at a venue we can actually act on, so that IF a hedgeable coin's funding
ever spikes far enough to clear cost (e.g. a liquidation cascade driving BTC/ETH funding
to an extreme), we catch it in real time instead of finding out weeks later. Costs nothing
when quiet; strictly better than only watching a venue we are barred from trading.

THE GO CONDITION here needs NO borrow (that was OKX's blocker): positive funding -> short
the perp, hedge by BUYING spot. So the flag is simply: hedgeable coin whose funding clears
a cost-aware threshold, in the direction the spot hedge supports.

All data from Delta's public API (no auth), reachable from India and from cloud runners.
"""
from __future__ import annotations

import csv
import json
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

TICKERS = ("https://api.india.delta.exchange/v2/tickers"
           "?contract_types=perpetual_futures")
SPOT = "https://api.india.delta.exchange/v2/products?contract_types=spot"

# Delta India round-trip cost for a delta-neutral pair, honest estimate:
#   perp taker ~0.05%/side + spot taker ~0.05%/side, entry and exit = ~0.4% round trip.
# Funding is per 8h (3/day). To clear 0.4% over, say, a 3-day hold we need the DAILY
# funding to beat cost/3 plus a margin. Flag when annualized funding on a HEDGEABLE coin
# exceeds this — a deliberately high bar so baseline (10.95%/yr) never trips it.
GO_ANNUAL_FUNDING_PCT = 50.0     # ~0.137%/day; baseline is 0.03%/day, so ~4.5x baseline

STORE = Path(__file__).resolve().parents[2] / "data" / "delta"
SNAP = STORE / "delta_funding.csv"
FIELDS = ["ts", "symbol", "funding_pct_8h", "annual_funding_pct", "mark_price",
          "hedgeable", "go"]


def _get(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def hedgeable_bases() -> set[str]:
    """Coins with a Delta SPOT market — the only ones a no-borrow hedge is possible on."""
    try:
        spot = _get(SPOT).get("result", [])
    except Exception:
        return set()
    return {(p.get("underlying_asset") or {}).get("symbol") for p in spot} - {None}


def step() -> dict:
    """One snapshot. Records every perp's funding; flags hedgeable coins above the bar."""
    try:
        tk = _get(TICKERS).get("result", [])
    except Exception as e:
        return {"ok": False, "reason": f"Delta unreachable: {str(e)[:50]}"}
    if not tk:
        return {"ok": False, "reason": "no tickers"}

    bases = hedgeable_bases()
    ts = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows, gos = [], []
    for x in tk:
        sym = x.get("symbol", "")
        try:
            fr = float(x.get("funding_rate") or 0)          # % per 8h
            mark = float(x.get("mark_price") or 0)
        except (TypeError, ValueError):
            continue
        base = sym.replace("USD", "")
        hedgeable = base in bases
        annual = fr * 3 * 365
        # GO: hedgeable AND funding rich enough to clear cost. Direction is implicit —
        # positive funding => short perp + buy spot; negative => long perp + sell spot
        # (sell needs spot inventory, so positive is the clean, borrow-free case).
        go = hedgeable and annual >= GO_ANNUAL_FUNDING_PCT
        if go:
            gos.append({"symbol": sym, "annual_funding_pct": round(annual, 1),
                        "funding_pct_8h": round(fr, 4)})
        # only persist hedgeable coins (the tradeable universe) — keeps the file small
        if hedgeable:
            rows.append({"ts": ts, "symbol": sym, "funding_pct_8h": round(fr, 5),
                         "annual_funding_pct": round(annual, 2), "mark_price": mark,
                         "hedgeable": True, "go": go})

    STORE.mkdir(parents=True, exist_ok=True)
    new = not SNAP.exists()
    with open(SNAP, "a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerows(rows)

    return {"ok": True, "perps": len(tk), "hedgeable": len(bases),
            "recorded": len(rows), "go_signals": gos}
