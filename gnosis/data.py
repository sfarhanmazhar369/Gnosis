"""Inputs for the analyst: recent bars and headlines from Alpaca's market data API.

Keep inputs tight. The model needs specific, recent information, not a day of noise.
Swap this module out for whatever news source you trust.
"""

from datetime import datetime, timedelta, timezone
from functools import lru_cache

from alpaca.data.historical.news import NewsClient
from alpaca.data.historical.stock import StockHistoricalDataClient
from alpaca.data.requests import NewsRequest, StockBarsRequest, StockLatestTradeRequest
from alpaca.data.timeframe import TimeFrame, TimeFrameUnit

from gnosis.broker import _keys

MAX_HEADLINES = 10
MAX_SUMMARY_CHARS = 1500


@lru_cache(maxsize=1)
def _stock_client() -> StockHistoricalDataClient:
    return StockHistoricalDataClient(*_keys())


@lru_cache(maxsize=1)
def _news_client() -> NewsClient:
    return NewsClient(*_keys())


def latest_price(symbol: str) -> float:
    trades = _stock_client().get_stock_latest_trade(
        StockLatestTradeRequest(symbol_or_symbols=symbol)
    )
    return float(trades[symbol].price)


def market_summary(symbol: str) -> str:
    now = datetime.now(timezone.utc)
    daily = _stock_client().get_stock_bars(StockBarsRequest(
        symbol_or_symbols=symbol, timeframe=TimeFrame.Day, start=now - timedelta(days=30),
    )).data.get(symbol, [])
    intraday = _stock_client().get_stock_bars(StockBarsRequest(
        symbol_or_symbols=symbol, timeframe=TimeFrame(15, TimeFrameUnit.Minute),
        start=now - timedelta(days=1),
    )).data.get(symbol, [])

    def fmt(b) -> str:
        return (f"{b.timestamp:%Y-%m-%d %H:%M} O={b.open:.2f} H={b.high:.2f} "
                f"L={b.low:.2f} C={b.close:.2f} V={int(b.volume)}")

    lines = ["Daily bars (last 30 days):", *map(fmt, daily[-20:]),
             "15-minute bars (last day):", *map(fmt, intraday[-16:])]
    return "\n".join(lines)


def headlines(symbol: str, since: timedelta = timedelta(days=1)) -> list[str]:
    news = _news_client().get_news(NewsRequest(
        symbols=symbol, start=datetime.now(timezone.utc) - since, limit=MAX_HEADLINES,
    ))
    items = news.data.get("news", []) if hasattr(news, "data") else []
    out = []
    for n in items[:MAX_HEADLINES]:
        summary = (n.summary or "")[:MAX_SUMMARY_CHARS]
        out.append(f"[{n.created_at:%Y-%m-%d %H:%M} UTC | {n.source}] {n.headline}\n{summary}\n{n.url or ''}")
    return out


def get_inputs(symbol: str) -> tuple[str, list[str], float]:
    """Return (market_data, news_items, price)."""
    price = latest_price(symbol)
    market_data = f"Last trade: {price:.2f}\n" + market_summary(symbol)
    return market_data, headlines(symbol), price
