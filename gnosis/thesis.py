"""A trade idea is a typed object, not a paragraph."""

from typing import Literal

from pydantic import BaseModel


class TradeThesis(BaseModel):
    symbol: str
    action: Literal["buy", "sell", "hold"]
    confidence: Literal["low", "medium", "high"]
    entry_reason: str
    stop_loss: float
    invalidation: str    # what would prove this thesis wrong
    sources: list[str]   # which inputs support it


def hold(symbol: str, reason: str) -> TradeThesis:
    """A synthetic no-trade thesis, used when the analyst can't produce one."""
    return TradeThesis(
        symbol=symbol,
        action="hold",
        confidence="low",
        entry_reason=reason,
        stop_loss=0.0,
        invalidation="n/a",
        sources=[],
    )
