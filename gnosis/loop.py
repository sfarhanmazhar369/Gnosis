"""The session loop: data in, thesis out, risk check, order, journal.

    python -m gnosis.loop          # run continuously
    python -m gnosis.loop --once   # one cycle, then exit
"""

import argparse
import logging
import time

from gnosis import config
from gnosis.analyst import analyze
from gnosis.journal import journal, queue_pending
from gnosis.killswitch import kill_switch_engaged
from gnosis.research import load_brief
from gnosis.risk import check_trade

log = logging.getLogger(__name__)


def process_symbol(symbol: str, account) -> None:
    from gnosis.broker import execute
    from gnosis.data import get_inputs

    market_data, news, price = get_inputs(symbol)
    thesis = analyze(symbol, market_data, news, research_brief=load_brief(symbol))
    approved, qty, reason = check_trade(thesis, account, price)

    if not approved:
        journal(thesis, False, qty, reason, price=price, status="rejected")
        return

    if config.REQUIRE_MANUAL_APPROVAL:
        queue_pending(thesis, qty, price)
        journal(thesis, True, qty, reason, price=price, status="pending")
    else:
        try:
            order = execute(thesis, qty)
        except Exception as e:
            log.exception("Order failed for %s", symbol)
            journal(thesis, True, qty, f"{reason} Order failed: {e}", price=price, status="error")
            return
        journal(thesis, True, qty, reason, price=price, order_id=order.id, status="submitted")

    # Count the slot as used either way, so one cycle can't queue past the limit.
    account.open_positions += 1
    account.held_symbols.add(symbol.upper())


def run_cycle(watchlist: list[str]) -> bool:
    """Return False when the system should stop."""
    from gnosis.broker import account_state, trading_client

    if kill_switch_engaged():
        log.warning("Kill switch engaged. Orders cancelled, positions closed. Stopping.")
        return False

    if not trading_client().get_clock().is_open:
        return True  # overnight research runs separately (gnosis.research)

    account = account_state()
    if config.REQUIRE_MANUAL_APPROVAL:
        # Don't re-queue an idea every cycle while it waits for a human.
        from gnosis.approve import pending_symbols_today

        account.held_symbols |= pending_symbols_today()
    for symbol in watchlist:
        try:
            process_symbol(symbol, account)
        except Exception:
            # One bad symbol (data outage, etc.) never takes down the cycle.
            log.exception("Cycle failed for %s", symbol)
    return True


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    args = ap.parse_args()

    while run_cycle(config.WATCHLIST) and not args.once:
        time.sleep(config.CYCLE_SECONDS)


if __name__ == "__main__":
    main()
