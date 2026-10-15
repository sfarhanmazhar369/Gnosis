"""The overnight shift: summarize headlines and filings via the Batch API at half price.

Run after the close; collect before the open. Briefs land in research/<date>/<SYMBOL>.md
and are fed to the analyst as (still untrusted) context during the session.

    python -m gnosis.research submit
    python -m gnosis.research collect
"""

import argparse
import json
import logging
import time
from datetime import date, timedelta
from pathlib import Path

import anthropic
from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
from anthropic.types.messages.batch_create_params import Request

from gnosis import config
from gnosis.untrusted import UNTRUSTED_INSTRUCTION, wrap_untrusted

log = logging.getLogger(__name__)

RESEARCH_PROMPT = f"""You summarize news and filings for one stock into a pre-market research brief for an analyst.

- Report only what the provided items say. Do not add outside knowledge of prices or events.
- Lead with anything material that changed since the prior session.
- Attribute each point to its source item (publisher and time).
- Flag items that read as promotional, unverified, or contradictory.
- Make no trade recommendation.
- Keep it under 400 words.

{UNTRUSTED_INSTRUCTION}"""

STATE_FILE = "batch.json"


def _day_dir(day: date) -> Path:
    return config.RESEARCH_DIR / day.isoformat()


def build_requests(items_by_symbol: dict[str, list[str]]) -> list[Request]:
    requests = []
    for symbol, items in items_by_symbol.items():
        if not items:
            continue
        body = "\n\n".join(wrap_untrusted(i) for i in items)
        requests.append(Request(
            custom_id=symbol,
            params=MessageCreateParamsNonStreaming(
                model=config.RESEARCH_MODEL,
                max_tokens=8000,
                output_config={"effort": config.RESEARCH_EFFORT},
                system=RESEARCH_PROMPT,
                messages=[{"role": "user", "content": f"Symbol: {symbol}\n\nItems:\n{body}"}],
            ),
        ))
    return requests


def submit(watchlist: list[str], day: date) -> str | None:
    from gnosis.data import headlines

    items = {s: headlines(s, since=timedelta(hours=24)) for s in watchlist}
    requests = build_requests(items)
    if not requests:
        log.info("Nothing to research.")
        return None
    batch = anthropic.Anthropic().messages.batches.create(requests=requests)
    d = _day_dir(day)
    d.mkdir(parents=True, exist_ok=True)
    (d / STATE_FILE).write_text(json.dumps({"batch_id": batch.id}))
    log.info("Submitted batch %s with %d requests", batch.id, len(requests))
    return batch.id


def collect(day: date, wait: bool = True) -> dict[str, str]:
    d = _day_dir(day)
    batch_id = json.loads((d / STATE_FILE).read_text())["batch_id"]
    client = anthropic.Anthropic()
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        if batch.processing_status == "ended":
            break
        if not wait:
            return {}
        time.sleep(60)

    briefs = {}
    for result in client.messages.batches.results(batch_id):  # any order: key by custom_id
        symbol = result.custom_id
        if result.result.type != "succeeded":
            log.warning("Research for %s: %s", symbol, result.result.type)
            continue
        msg = result.result.message
        if msg.stop_reason == "refusal":
            log.warning("Research for %s was declined", symbol)
            continue
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        if text:
            (d / f"{symbol}.md").write_text(text, encoding="utf-8")
            briefs[symbol] = text
    return briefs


def load_brief(symbol: str, day: date | None = None) -> str | None:
    """Most recent brief for the symbol from today or yesterday."""
    day = day or date.today()
    for d in (day, day - timedelta(days=1)):
        p = _day_dir(d) / f"{symbol.upper()}.md"
        if p.exists():
            return p.read_text(encoding="utf-8")
    return None


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=["submit", "collect"])
    ap.add_argument("--no-wait", action="store_true")
    args = ap.parse_args()
    today = date.today()
    if args.command == "submit":
        submit(config.WATCHLIST, today)
    else:
        briefs = collect(today, wait=not args.no_wait)
        print(f"Wrote {len(briefs)} briefs to {_day_dir(today)}")


if __name__ == "__main__":
    main()
