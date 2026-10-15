"""The analyst: reads data and news, writes a structured thesis.

It recommends. It never sizes a position and never places an order.
"""

import logging

import anthropic

from gnosis import config
from gnosis.thesis import TradeThesis, hold
from gnosis.untrusted import UNTRUSTED_INSTRUCTION, wrap_untrusted

log = logging.getLogger(__name__)

ANALYST_PROMPT = f"""You are a disciplined equity analyst producing trade theses for a rules-based system. You recommend; you never size positions or place orders.

Standards:
- Base every claim only on the market data, research brief, and news provided. Do not use outside knowledge of prices or events.
- Default to "hold". Recommend "buy" or "sell" only when the evidence is specific, recent, and clearly material.
- Set stop_loss at the price where your thesis is clearly wrong, not where it hurts. For "hold", set stop_loss to 0.
- State the invalidation condition concretely.
- List the specific inputs that support the thesis in sources.
- Use "high" confidence rarely. Most days, nothing deserves it.

{UNTRUSTED_INSTRUCTION}"""

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic()
    return _client


def build_user_message(
    symbol: str, market_data: str, news_items: list[str], research_brief: str | None
) -> str:
    news_block = "\n\n".join(wrap_untrusted(item) for item in news_items) or "(no news)"
    parts = [f"Symbol: {symbol}", f"Market data:\n{market_data}"]
    if research_brief:
        # The brief is a model summary of untrusted text, so it stays wrapped.
        parts.append(f"Overnight research brief:\n{wrap_untrusted(research_brief)}")
    parts.append(f"News:\n{news_block}")
    parts.append("Produce a trade thesis.")
    return "\n\n".join(parts)


def analyze(
    symbol: str,
    market_data: str,
    news_items: list[str],
    research_brief: str | None = None,
) -> TradeThesis:
    """Return a thesis. Any failure to get one becomes a hold, never a trade."""
    try:
        response = _get_client().beta.messages.parse(
            model=config.ANALYST_MODEL,
            max_tokens=16000,
            system=ANALYST_PROMPT,
            messages=[{
                "role": "user",
                "content": build_user_message(symbol, market_data, news_items, research_brief),
            }],
            output_format=TradeThesis,
            output_config={"effort": config.ANALYST_EFFORT},
            # If a safety classifier declines, retry server-side on the
            # recommended fallback model instead of returning nothing.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.APIError as e:
        log.exception("Analyst call failed for %s", symbol)
        return hold(symbol, f"Analyst unavailable: {type(e).__name__}")

    if response.stop_reason == "refusal":
        return hold(symbol, "Analyst declined the request.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        return hold(symbol, f"No usable thesis (stop_reason={response.stop_reason}).")

    thesis = response.parsed_output
    if thesis.symbol.upper() != symbol.upper():
        # The model was asked about one symbol; a thesis on another is a red flag.
        return hold(symbol, f"Analyst returned a thesis for {thesis.symbol}; discarded.")
    return thesis
