"""Emergency brake. Create a file named KILL and the next cycle flattens everything.

Trigger it by hand, from a phone through any file-sync tool, or from your own
monitoring. The daily loss limit is the automatic brake; this is the manual one.
"""

from pathlib import Path

from gnosis import config


def kill_requested(path: Path | None = None) -> bool:
    return (path or config.KILL_FILE).exists()


def kill_switch_engaged(path: Path | None = None) -> bool:
    if not kill_requested(path):
        return False
    from gnosis.broker import trading_client

    trading_client().close_all_positions(cancel_orders=True)
    return True
