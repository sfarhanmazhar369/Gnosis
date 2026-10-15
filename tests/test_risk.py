import pytest

from gnosis import config
from gnosis.risk import Account, check_trade
from gnosis.thesis import TradeThesis


def thesis(**kw):
    base = dict(symbol="NVDA", action="buy", confidence="high", entry_reason="r",
                stop_loss=170.0, invalidation="i", sources=["s"])
    base.update(kw)
    return TradeThesis.model_construct(**base)


def acct(**kw):
    base = dict(equity=100_000.0, day_pnl=0.0, open_positions=0)
    base.update(kw)
    return Account(**base)


def test_worked_example_takes_smaller_of_risk_and_size():
    # $180 entry, $170 stop: 1% risk allows 100 shares, 5% size allows 27.
    assert check_trade(thesis(), acct(), 180.0) == (True, 27, "Approved by risk engine.")


def test_risk_cap_binds_when_size_cap_is_loose(monkeypatch):
    # With the default 1%/5% pair the size cap binds for any stop under 20% away,
    # so loosen the size cap to show the risk rule doing the sizing.
    monkeypatch.setattr(config, "MAX_POSITION_PCT", 0.25)
    # $100 entry, $90 stop: risk allows 1000/10 = 100 shares, size allows 250.
    assert check_trade(thesis(stop_loss=90.0), acct(), 100.0)[:2] == (True, 100)


def test_daily_loss_limit_halts_everything():
    ok, qty, reason = check_trade(thesis(), acct(day_pnl=-3_000.0), 180.0)
    assert not ok and qty == 0 and "Daily loss" in reason


@pytest.mark.parametrize("kw,price,fragment", [
    (dict(symbol="GME"), 180.0, "not on the allowed list"),
    (dict(action="hold"), 180.0, "no trade"),
    (dict(confidence="medium"), 180.0, "confidence"),
    (dict(stop_loss=185.0), 180.0, "below entry"),
    (dict(stop_loss=0.0), 180.0, "Invalid stop"),
    (dict(stop_loss=100.0), 180.0, "too far"),
    (dict(action="sell", stop_loss=190.0), 180.0, "Short selling is disabled"),
    (dict(), 0.0, "No valid price"),
])
def test_rejections(kw, price, fragment):
    ok, qty, reason = check_trade(thesis(**kw), acct(), price)
    assert not ok and qty == 0 and fragment in reason


def test_enum_casing_is_ignored():
    ok, _, _ = check_trade(thesis(action="BUY", confidence="High", symbol="nvda"), acct(), 180.0)
    assert ok


def test_position_limits():
    assert not check_trade(thesis(), acct(open_positions=config.MAX_OPEN_POSITIONS), 180.0)[0]
    assert not check_trade(thesis(), acct(held_symbols={"NVDA"}), 180.0)[0]


def test_shorts_when_enabled(monkeypatch):
    monkeypatch.setattr(config, "ALLOW_SHORTS", True)
    assert not check_trade(thesis(action="sell", stop_loss=170.0), acct(), 180.0)[0]
    ok, qty, _ = check_trade(thesis(action="sell", stop_loss=190.0), acct(), 180.0)
    assert ok and qty == 27


def test_too_small():
    ok, qty, reason = check_trade(thesis(), acct(equity=1_000.0), 180.0)
    assert not ok and "too small" in reason
