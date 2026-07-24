"""Is a coin actually borrowable RIGHT NOW? — read-only, no trade, no money.

    set OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE   (read-only key is enough)
    python scripts/borrow_check.py BARD

WHY THIS EXISTS. `funding_escalation` is our one surviving idea and its economics are now
MEASURED (BARD: +1.6163% net over a 14h episode, all 8 settlements above breakeven). One
question remains, and no amount of public data answers it:

    when the funding is pinned and everyone wants the same borrow, does it actually FILL?

OKX's public endpoints expose only the MAXIMUM quota and the base rate — never live pool
availability. That is a documented dead end (verified: rate is an administered tier, not a
market-clearing price; controls BTC/ETH/USDT showed exactly 1.0x variation over 649
observations). The authenticated endpoints below may expose the real number.

THE POINT: this needs an ACCOUNT, not a DEPOSIT. An OKX account with a READ-ONLY API key
and a zero balance costs nothing, and this script never places an order — it only reads.

SAFETY, deliberately:
  * Read-only endpoints only. There is no order/borrow/transfer call anywhere in this file.
  * Credentials come from environment variables you set locally. They are never written to
    disk by this script, never committed, and never leave your machine.
  * Use a key with TRADE PERMISSION DISABLED. This script does not need it, and a key that
    cannot trade cannot be misused.

HONEST CAVEAT ON WHAT THIS CAN AND CANNOT PROVE:
  `max-loan` computes against YOUR collateral. With a zero balance it will likely return 0 —
  and that is 0-because-you-have-no-collateral, NOT 0-because-the-pool-is-empty. The two are
  indistinguishable from the number alone. `interest-limits` is the more informative one: it
  reports per-currency loan quota and used amount at the account/VIP tier, which is closer to
  pool state. Read both, and treat a zero from `max-loan` on an empty account as UNINFORMATIVE
  rather than as evidence.

  The final question — does a real borrow fill during real stress — is only answerable with a
  real (tiny) borrow. That is the user's call and the user's money, not something this script
  or Claude should do.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

BASE = "https://www.okx.com"


def _ts() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.") + \
        f"{datetime.now(timezone.utc).microsecond // 1000:03d}Z"


def _signed_get(path: str, key: str, secret: str, passphrase: str) -> dict:
    """GET with OKX's HMAC signature. Read-only by construction — method is always GET."""
    ts = _ts()
    msg = f"{ts}GET{path}"
    sign = base64.b64encode(
        hmac.new(secret.encode(), msg.encode(), hashlib.sha256).digest()).decode()
    req = urllib.request.Request(BASE + path, headers={
        "OK-ACCESS-KEY": key,
        "OK-ACCESS-SIGN": sign,
        "OK-ACCESS-TIMESTAMP": ts,
        "OK-ACCESS-PASSPHRASE": passphrase,
        "Content-Type": "application/json",
        "User-Agent": "aitrader/0.1",
    })
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def public_quota(ccy: str) -> dict | None:
    """The public number we already track: max quota + base rate. No auth."""
    req = urllib.request.Request(
        BASE + "/api/v5/public/interest-rate-loan-quota",
        headers={"User-Agent": "aitrader/0.1"})
    with urllib.request.urlopen(req, timeout=15) as r:
        d = json.loads(r.read())
    for block in d.get("data", []):
        for row in block.get("basic", []) or []:
            if row.get("ccy") == ccy:
                return row
    return None


def main() -> None:
    ccy = (sys.argv[1] if len(sys.argv) > 1 else "BARD").upper()

    print(f"=== {ccy}: PUBLIC data (no auth needed) ===")
    pub = public_quota(ccy)
    if pub:
        print(f"  max quota : {float(pub['quota']):,.0f} {ccy}")
        print(f"  base rate : {float(pub['rate']) * 100:.4f}%/day")
        print("  ^ this is the CEILING, not what is available right now")
    else:
        print(f"  {ccy} is NOT in the public borrow list -> not borrowable at all.")
        print("  That alone is decisive: no borrow = no short-spot hedge = no trade.")
        return

    key = os.environ.get("OKX_API_KEY")
    secret = os.environ.get("OKX_API_SECRET")
    passphrase = os.environ.get("OKX_PASSPHRASE")
    if not (key and secret and passphrase):
        print("\n=== AUTHENTICATED check: SKIPPED ===")
        print("  Set these locally (read-only key, trade permission OFF), then re-run:")
        print("    OKX_API_KEY / OKX_API_SECRET / OKX_PASSPHRASE")
        print("  A free account with a ZERO balance is enough — no deposit required.")
        return

    print("\n=== AUTHENTICATED read-only checks (no order, no borrow) ===")
    for label, path in [
        ("interest-limits (closest to pool state)", "/api/v5/account/interest-limits"),
        (f"max-loan {ccy}-USDT cross",
         f"/api/v5/account/max-loan?instId={ccy}-USDT&mgnMode=cross"),
    ]:
        try:
            d = _signed_get(path, key, secret, passphrase)
        except Exception as e:
            print(f"  {label}: request failed — {str(e)[:70]}")
            continue
        if d.get("code") != "0":
            print(f"  {label}: code={d.get('code')} {d.get('msg', '')[:70]}")
            continue
        rows = d.get("data") or []
        if "interest-limits" in path:
            hit = False
            for blk in rows:
                for r in blk.get("records", []) or []:
                    if r.get("ccy") == ccy:
                        hit = True
                        print(f"  {label}:")
                        for k in ("ccy", "loanQuota", "usedLoan", "availLoan",
                                  "surplusLmt", "rate"):
                            if k in r:
                                print(f"      {k:12s} {r[k]}")
            if not hit:
                print(f"  {label}: {ccy} not present in records "
                      f"({len(rows)} tier blocks returned)")
        else:
            print(f"  {label}: {rows if rows else 'empty'}")
            print("      NOTE: on a zero-balance account a 0 here means 'no collateral',")
            print("      NOT 'pool empty'. Treat it as UNINFORMATIVE, not as evidence.")

    print("\n  Still open after this: whether a real borrow FILLS under stress.")
    print("  That needs a tiny real borrow — your account, your money, your call.")


if __name__ == "__main__":
    main()
