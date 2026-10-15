"""The risk engine. Pure code, no AI. It decides whether a trade happens and how big."""

from dataclasses import dataclass, field

from gnosis import config


@dataclass
class Account:
    equity: float
    day_pnl: float
    open_positions: int
    held_symbols: set[str] = field(default_factory=set)


def check_trade(thesis, account: Account, price: float) -> tuple[bool, int, str]:
    """Return (approved, qty, reason). The model never sizes a trade.

    Enum values are compared case-insensitively: structured outputs don't
    guarantee their casing.
    """
    symbol = thesis.symbol.upper()
    action = thesis.action.lower()

    if account.equity <= 0:
        return False, 0, "Account equity is not positive."
    if account.day_pnl <= -config.MAX_DAILY_LOSS_PCT * account.equity:
        return False, 0, "Daily loss limit hit. Trading halted for today."
    if symbol not in config.ALLOWED_SYMBOLS:
        return False, 0, f"{thesis.symbol} is not on the allowed list."
    if action == "hold":
        return False, 0, "Model recommends no trade."
    if action not in ("buy", "sell"):
        return False, 0, f"Unknown action {thesis.action!r}."
    if action == "sell" and not config.ALLOW_SHORTS:
        return False, 0, "Short selling is disabled."
    if symbol in account.held_symbols:
        return False, 0, f"Already holding {symbol}."
    if account.open_positions >= config.MAX_OPEN_POSITIONS:
        return False, 0, "Maximum open positions reached."
    if thesis.confidence.lower() != config.REQUIRED_CONFIDENCE:
        return False, 0, f"Only {config.REQUIRED_CONFIDENCE}-confidence theses are eligible."
    if price <= 0:
        return False, 0, "No valid price."

    stop = thesis.stop_loss
    if stop <= 0:
        return False, 0, "Invalid stop loss."
    if action == "buy" and stop >= price:
        return False, 0, "Stop loss must be below entry for a long."
    if action == "sell" and stop <= price:
        return False, 0, "Stop loss must be above entry for a short."

    stop_distance = abs(price - stop)
    if stop_distance > config.MAX_STOP_DISTANCE_PCT * price:
        return False, 0, "Stop loss is too far from entry."

    qty_by_risk = (config.MAX_RISK_PER_TRADE * account.equity) / stop_distance
    qty_by_size = (config.MAX_POSITION_PCT * account.equity) / price
    qty = int(min(qty_by_risk, qty_by_size))
    if qty < 1:
        return False, 0, "Position too small after risk sizing."
    return True, qty, "Approved by risk engine."
