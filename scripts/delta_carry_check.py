"""Does the funding HOLD? — one command, clear trade/no-trade read on Delta carry.

    python scripts/delta_carry_check.py                # hottest hedgeable coin
    python scripts/delta_carry_check.py XRPUSD         # a specific coin
    python scripts/delta_carry_check.py --file other.csv

Run this the moment a DELTA GO alert lands (or any time you want to check). It reads the
recorded funding history and tells you whether the richness lasted long enough to clear
the ~0.40% round-trip cost — the difference between a real carry and a one-print trap.

It NEVER places a trade. A CANDIDATE verdict means "take it to the napkin", not "trade".
"""
from __future__ import annotations

import sys
from pathlib import Path

# Windows consoles default to cp1252, which cannot encode the emoji/arrows below.
# Force UTF-8 on stdout so the report renders (or degrades) instead of crashing.
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from aitrader.research import delta_carry as dc  # noqa: E402

_ICON = {"CANDIDATE": "🟢", "WATCH": "🟡", "THIN": "🟠", "BELOW": "🔴", "FLIP": "⚪"}


def main() -> None:
    args = [a for a in sys.argv[1:]]
    path = dc.DEFAULT_CSV
    if "--file" in args:
        i = args.index("--file")
        path = Path(args[i + 1])
        del args[i:i + 2]
    symbol = args[0] if args else None

    rows = dc.load(path)
    if not rows:
        print(f"No data at {path}. (Collector abhi tak Delta funding record nahi kiya?)")
        return

    if symbol is None:
        symbol = dc.hottest(rows)
        if symbol is None:
            print("No hedgeable symbols in the file.")
            return

    res = dc.analyze(rows, symbol)
    if not res.get("ok"):
        print(f"{symbol}: {res.get('reason')}")
        return

    print(f"\n  Delta funding-carry check — {res['symbol']}")
    print(f"  as of {res['as_of']}   ({res['history_days']} din ka history, "
          f"{res['n_settlements_total']} settlements)")
    print(f"  abhi: {res['latest_annual']:+.1f}%/yr  ({res['latest_8h']:+.4f}%/8h)   "
          f"GO bar {res['go_bar_annual']:.0f}%/yr   round-trip cost {res['breakeven_cost_pct']:.2f}%")
    print("  " + "-" * 68)
    print(f"  {'window':<9}{'setts':>6}{'avg/8h':>10}{'cum funding':>13}"
          f"{'net-cost':>11}{'realized APR':>14}{'>=bar':>7}")
    for w in res["windows"]:
        print(f"  {str(w['days'])+'d':<9}{w['n']:>6}{w['avg_8h']:>9.4f}%"
              f"{w['cum']:>12.3f}%{w['net']:>+10.2f}%{w['apr']:>12.1f}%/yr"
              f"{w['above']:>4}/{w['n']:<2}")
    print("  " + "-" * 68)
    print("  net-cost = agar poora window hold karte: cumulative funding - 0.40% round trip.")
    print("  >=bar    = kitne settlements 50%/yr (=3-din breakeven) ke upar the.\n")

    v = res["verdict"]
    print(f"  {_ICON.get(v['code'], '•')}  VERDICT: {v['code']}")
    print(f"      {v['msg']}")
    if v["code"] == "CANDIDATE":
        print("      → agla kadam: napkin R8 (venue+legs) phir gauntlet. Trade sirf uske baad, "
              "chhoti size, tumhare haath.")
    else:
        print("      → abhi kuch nahi karna. Machine watch karti rahegi; alert phir aayega.")
    print()


if __name__ == "__main__":
    main()
