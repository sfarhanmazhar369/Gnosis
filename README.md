# Gnosis

A 24/7 research-and-trading loop for a **paper** account. Claude reads every headline on the watchlist and writes a structured trade thesis. Plain Python decides whether a trade happens and how big it is. Every decision is journaled, including the ones the system refused.

> **Not financial advice.** Most trading strategies lose money, automated ones included. This build is paper-only (`config.PAPER = True`, and `broker.trading_client()` refuses to start otherwise). Run it for weeks before you trust it.

## Who does what

| Layer | Owner | Job |
|---|---|---|
| Analyst | Claude Opus 5.5 (`gnosis/analyst.py`) | Reads bars, news, and the overnight brief. Returns a `TradeThesis`: action, confidence, stop, invalidation, sources. |
| Overnight research | Claude Sonnet 5.5 via the Batch API (`gnosis/research.py`) | Summarizes the last 24h of headlines per symbol at batch prices. |
| Risk engine | Plain Python (`gnosis/risk.py`) | Applies the rules in `gnosis/config.py` and sizes the position. No model involved. |
| Executor | Alpaca paper (`gnosis/broker.py`) | Market entry with an OTO stop loss attached to the order. |
| Journal | `journal.jsonl` | Every thesis, verdict, and order, including holds and rejections. |
| Kill switch | `KILL` file | Next cycle cancels orders, closes all positions, and stops. |

**The model never sizes a position and never places an order.**

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
export ANTHROPIC_API_KEY=...
export ALPACA_API_KEY=...       # paper account keys
export ALPACA_SECRET_KEY=...
pytest
```

## Running it

```bash
# After the close: summarize headlines overnight (Batch API, half price)
python -m gnosis.research submit
# Before the open: collect the briefs into research/<date>/<SYMBOL>.md
python -m gnosis.research collect

# During the session: a cycle every 15 minutes
python -m gnosis.loop            # or --once for a single cycle

# Manual-approval mode (the default): review and sign off
python -m gnosis.approve         # list today's pending trades
python -m gnosis.approve 0       # re-check entry 0 at the current price, then submit

# Emergency stop
touch KILL
```

Schedule `research submit` / `collect` and `loop` with cron, systemd timers, or whatever you already use.

## The rules (`gnosis/config.py`)

- 5% max position, 1% max risk per trade, 3% daily loss halts trading, 5 open positions max.
- Stops more than 15% from entry are rejected.
- Only `high`-confidence theses are eligible. Default is `hold`.
- Long-only (`ALLOW_SHORTS = False`). With shorts on, a short's stop must sit above entry.
- No adding to a symbol already held, or already queued for approval today.
- `REQUIRE_MANUAL_APPROVAL = True`: approved trades go to `pending.jsonl` until you sign them.

Worked example: $100k equity, buy at $180, stop $170 → 1% risk allows 100 shares, 5% size allows 27 → **27 shares**.

Note: with 1% risk and 5% size, the size cap binds for any stop closer than 20% from entry, and the stop cap is 15%. So with the defaults, the position-size rule always decides the quantity, and the most a stopped-out trade can lose is 5% × 15% = 0.75% of equity. Tune the pair together.

## Safety details

- **Untrusted input.** Every headline and the overnight brief are wrapped in `<external_content id="…">` tags with a random id, and the system prompt tells the model never to follow instructions inside them. Forged closing tags in the payload are neutralized. The real backstop is that a hijacked analyst still can't size or place anything.
- **Failure means hold.** API errors, refusals, truncated output, or a thesis for a different symbol all become a journaled `hold`.
- **Refusal fallback.** Analyst calls opt into server-side fallbacks (`fallbacks="default"`, beta `server-side-fallback-2026-07-01`). If a safety classifier declines, the API retries on Anthropic's recommended fallback model. Remove those two arguments if you'd rather a decline just become a hold.
- **Effort.** The analyst runs at `medium` (Opus 5.5's default, set explicitly). Compare effort levels against the journal before raising it.

## Don't backtest the model

An LLM may have read how the story ended, so historical backtests of its judgment are contaminated. Forward-test on paper instead. You *can* backtest the pure-code parts (risk rules, sizing). `tests/test_risk.py` does exactly that.
