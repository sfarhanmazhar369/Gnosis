"""Every decision gets written down, including the trades the system refused."""

import json
from datetime import datetime, timezone
from pathlib import Path

from gnosis import config


def _append(path: Path, entry: dict) -> None:
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


def journal(
    thesis,
    approved: bool,
    qty: int,
    reason: str,
    *,
    price: float | None = None,
    order_id=None,
    status: str | None = None,
    path: Path | None = None,
) -> dict:
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "thesis": thesis.model_dump(),
        "price": price,
        "approved": approved,
        "qty": qty,
        "risk_reason": reason,
        "status": status,  # submitted | pending | rejected | error
        "order_id": str(order_id) if order_id else None,
        "model": config.ANALYST_MODEL,
    }
    _append(path or config.JOURNAL_FILE, entry)
    return entry


def queue_pending(thesis, qty: int, price: float, path: Path | None = None) -> dict:
    """Manual-approval mode: write the trade for a human to sign off on."""
    entry = {
        "time": datetime.now(timezone.utc).isoformat(),
        "thesis": thesis.model_dump(),
        "qty": qty,
        "price_at_approval": price,
    }
    _append(path or config.PENDING_FILE, entry)
    return entry
