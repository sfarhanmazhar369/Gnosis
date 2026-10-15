"""Manual approval for queued trades. You keep the final signature.

    python -m gnosis.approve            # list today's pending trades
    python -m gnosis.approve 0 2        # submit entries 0 and 2

Each approved entry is re-checked by the risk engine at the current price
before submission, since the market has moved since it was queued.
"""

import argparse
import json
from datetime import datetime, timezone

from gnosis import config
from gnosis.journal import journal
from gnosis.risk import check_trade
from gnosis.thesis import TradeThesis


def pending_today() -> list[dict]:
    if not config.PENDING_FILE.exists():
        return []
    today = datetime.now(timezone.utc).date().isoformat()
    entries = [json.loads(line) for line in config.PENDING_FILE.read_text().splitlines() if line]
    return [e for e in entries if e["time"].startswith(today)]


def pending_symbols_today() -> set[str]:
    return {e["thesis"]["symbol"].upper() for e in pending_today()}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("indexes", nargs="*", type=int)
    args = ap.parse_args()

    entries = pending_today()
    if not args.indexes:
        for i, e in enumerate(entries):
            t = e["thesis"]
            print(f"[{i}] {e['time']} {t['action'].upper()} {e['qty']} {t['symbol']} "
                  f"@~{e['price_at_approval']:.2f} stop {t['stop_loss']:.2f}\n"
                  f"     why: {t['entry_reason']}\n     wrong if: {t['invalidation']}")
        return

    from gnosis.broker import account_state, execute
    from gnosis.data import latest_price

    account = account_state()
    for i in args.indexes:
        thesis = TradeThesis(**entries[i]["thesis"])
        price = latest_price(thesis.symbol)
        approved, qty, reason = check_trade(thesis, account, price)
        if not approved:
            print(f"[{i}] {thesis.symbol}: rejected on re-check: {reason}")
            journal(thesis, False, qty, f"Manual re-check: {reason}", price=price, status="rejected")
            continue
        order = execute(thesis, qty)
        journal(thesis, True, qty, f"Manually approved. {reason}", price=price,
                order_id=order.id, status="submitted")
        account.open_positions += 1
        account.held_symbols.add(thesis.symbol.upper())
        print(f"[{i}] {thesis.symbol}: submitted {qty} shares, order {order.id}")


if __name__ == "__main__":
    main()
