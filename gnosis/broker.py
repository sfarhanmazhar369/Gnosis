"""Alpaca clients and the executor. Paper account only."""

import os
from functools import lru_cache

from alpaca.trading.client import TradingClient
from alpaca.trading.enums import OrderClass, OrderSide, TimeInForce
from alpaca.trading.requests import MarketOrderRequest, StopLossRequest

from gnosis import config
from gnosis.risk import Account
from gnosis.thesis import TradeThesis


def _keys() -> tuple[str, str]:
    return os.environ["ALPACA_API_KEY"], os.environ["ALPACA_SECRET_KEY"]


@lru_cache(maxsize=1)
def trading_client() -> TradingClient:
    if not config.PAPER:
        raise RuntimeError("config.PAPER is False. Live trading is not enabled in this build.")
    key, secret = _keys()
    return TradingClient(key, secret, paper=True)


def account_state() -> Account:
    trading = trading_client()
    acct = trading.get_account()
    positions = trading.get_all_positions()
    return Account(
        equity=float(acct.equity),
        day_pnl=float(acct.equity) - float(acct.last_equity),
        open_positions=len(positions),
        held_symbols={p.symbol.upper() for p in positions},
    )


def execute(thesis: TradeThesis, qty: int):
    """Submit the entry with the stop attached, so protection exists even if we crash.

    OTO ("one triggers other"): when the entry fills, the stop is placed.
    """
    order = MarketOrderRequest(
        symbol=thesis.symbol.upper(),
        qty=qty,
        side=OrderSide.BUY if thesis.action.lower() == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
        order_class=OrderClass.OTO,
        stop_loss=StopLossRequest(stop_price=round(thesis.stop_loss, 2)),
    )
    return trading_client().submit_order(order_data=order)
