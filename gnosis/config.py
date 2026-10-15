"""Rules written in advance. Edit these before you ever see a trade, never during one.

Rules decided in advance are rules. Rules decided in the moment are moods.
"""

from pathlib import Path

# --- Risk limits (enforced by gnosis.risk, never by a model) ---------------
MAX_POSITION_PCT = 0.05      # no single position above 5% of equity
MAX_RISK_PER_TRADE = 0.01    # never risk more than 1% of equity on one trade
MAX_DAILY_LOSS_PCT = 0.03    # stop all trading after a 3% down day
MAX_OPEN_POSITIONS = 5
MAX_STOP_DISTANCE_PCT = 0.15  # reject stops further than 15% from entry
ALLOW_SHORTS = False         # "sell" theses are rejected unless this is True
REQUIRED_CONFIDENCE = "high"  # only theses at this confidence are eligible

ALLOWED_SYMBOLS = frozenset({"AAPL", "MSFT", "NVDA", "SPY", "QQQ"})
WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY", "QQQ"]

# --- Execution ------------------------------------------------------------
# Paper trading only. Do not change until you have weeks of paper results.
PAPER = True
# Phase one: approved trades go to PENDING_FILE for a human to sign off on
# instead of being submitted. Flip to False only once the journal earns it.
REQUIRE_MANUAL_APPROVAL = True

CYCLE_SECONDS = 15 * 60  # one cycle every 15 minutes during market hours

# --- Models ---------------------------------------------------------------
ANALYST_MODEL = "claude-opus-5-5"       # writes the thesis
ANALYST_EFFORT = "medium"               # raise only after comparing in the journal
RESEARCH_MODEL = "claude-sonnet-5-5"    # summarizes filings/headlines overnight
RESEARCH_EFFORT = "medium"

# --- Files ----------------------------------------------------------------
DATA_DIR = Path(".")
JOURNAL_FILE = DATA_DIR / "journal.jsonl"
PENDING_FILE = DATA_DIR / "pending.jsonl"
KILL_FILE = DATA_DIR / "KILL"
RESEARCH_DIR = DATA_DIR / "research"
